from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ican.indexing.model import file_digest
from ican.indexing.schema import FileIdentity
from ican.ingestion.pipeline import confined, write_json


class RerankerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: Literal["BAAI/bge-reranker-v2-m3"]
    revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    local_path: str
    ledger_path: str
    files: dict[str, FileIdentity] = Field(min_length=1)
    device: Literal["cuda", "cpu"] = "cuda"
    precision: Literal["float16", "float32"] = "float16"
    batch_size: int = Field(default=2, ge=1, le=8)
    max_pair_tokens: int = Field(default=1536, ge=128, le=8192)


def model_files(root: Path, config: RerankerConfig) -> dict:
    directory = confined(root, config.local_path, "data/cache")
    found = {}
    for name, identity in config.files.items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("Reranker file unavailable or outside snapshot")
        if path.stat().st_size != identity.size:
            raise ValueError(f"Reranker size mismatch: {name}")
        digest = file_digest(path)
        if identity.sha256 and identity.sha256 != digest:
            raise ValueError(f"Reranker SHA mismatch: {name}")
        if identity.git_blob_sha1:
            blob = hashlib.sha1(
                f"blob {identity.size}\0".encode() + path.read_bytes()
            ).hexdigest()
            if blob != identity.git_blob_sha1:
                raise ValueError(f"Reranker blob mismatch: {name}")
        found[name] = {"bytes": identity.size, "sha256": digest}
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if (
            path.is_file()
            and relative.parts[0] != ".cache"
            and relative.as_posix() not in config.files
        ):
            raise ValueError("Unverified file in reranker snapshot")
    return found


def prepare_reranker(root: Path, config: RerankerConfig, *, http_ranges=False) -> dict:
    from huggingface_hub import snapshot_download

    directory = confined(root, config.local_path, "data/cache")
    snapshot_download(
        config.repository,
        revision=config.revision,
        local_dir=directory,
        allow_patterns=[
            n for n in config.files if not http_ranges or n != "model.safetensors"
        ],
        max_workers=3,
    )
    if http_ranges and not (directory / "model.safetensors").exists():
        from .download import download_ranges

        download_ranges(root, config, "model.safetensors")
    ledger = {
        "repository": config.repository,
        "revision": config.revision,
        "local_path": config.local_path,
        "license": "Apache-2.0",
        "source": f"https://huggingface.co/{config.repository}/tree/{config.revision}",
        "files": model_files(root, config),
        "backend": "transformers sequence-classification",
    }
    path = confined(root, config.ledger_path, "data/catalog")
    if path.is_symlink() or (path.exists() and path.stat().st_nlink > 1):
        raise ValueError("Reranker ledger cannot be linked")
    write_json(path, ledger)
    return ledger


def checked_scores(scores, count: int) -> list[float]:
    values = np.asarray(scores, dtype=np.float32)
    if values.shape != (count,) or not np.isfinite(values).all():
        raise ValueError("Reranker must return one finite logit per candidate")
    return values.tolist()


class LocalReranker:
    def __init__(self, root: Path, config: RerankerConfig):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = confined(root, config.ledger_path, "data/catalog")
        ledger = json.loads(path.read_text(encoding="utf-8"))
        files = model_files(root, config)
        if (
            ledger["repository"],
            ledger["revision"],
            ledger["local_path"],
            ledger["files"],
        ) != (config.repository, config.revision, config.local_path, files):
            raise ValueError("Reranker ledger differs from snapshot")
        if config.device == "cuda" and not torch.cuda.is_available():
            raise ValueError("Configured reranker CUDA unavailable")
        if config.device == "cpu" and config.precision != "float32":
            raise ValueError("CPU reranker requires float32")
        self.config = config
        self.lock = Lock()
        directory = str(confined(root, config.local_path, "data/cache"))
        self.tokenizer = AutoTokenizer.from_pretrained(
            directory, local_files_only=True, trust_remote_code=False
        )
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(
                directory,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                torch_dtype=torch.float16
                if config.precision == "float16"
                else torch.float32,
            )
            .to(config.device)
            .eval()
        )
        if self.model.config.num_labels != 1:
            raise ValueError("Reranker expected single-logit classification head")
        self.descriptor = {
            "repository": config.repository,
            "revision": config.revision,
            "ledger_sha256": file_digest(path),
            "max_pair_tokens": config.max_pair_tokens,
            "precision": config.precision,
            "batch_size": config.batch_size,
        }

    def score(self, query: str, passages: list[str]) -> tuple[list[float], dict]:
        import torch

        pairs = [[query, passage] for passage in passages]
        if not pairs:
            return [], {"truncated_pairs": 0, "max_pair_length": 0}
        with self.lock, torch.inference_mode():
            lengths = [
                len(ids)
                for ids in self.tokenizer(pairs, truncation=False, padding=False)[
                    "input_ids"
                ]
            ]
            scores = []
            for start in range(0, len(pairs), self.config.batch_size):
                inputs = self.tokenizer(
                    pairs[start : start + self.config.batch_size],
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_pair_tokens,
                    return_tensors="pt",
                ).to(self.config.device)
                scores.extend(
                    self.model(**inputs, return_dict=True)
                    .logits.view(-1)
                    .float()
                    .cpu()
                    .tolist()
                )
        return checked_scores(scores, len(passages)), {
            "truncated_pairs": sum(n > self.config.max_pair_tokens for n in lengths),
            "max_pair_length": max(lengths),
            "pair_n": len(pairs),
        }
