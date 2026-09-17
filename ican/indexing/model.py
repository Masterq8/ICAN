from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined, write_json

from .schema import ModelConfig


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_model_files(root: Path, config: ModelConfig) -> dict:
    directory = confined(root, config.local_path, "data/cache")
    for candidate in directory.rglob("*"):
        relative = candidate.relative_to(directory)
        if (
            candidate.is_file()
            and relative.parts[0] != ".cache"
            and relative.as_posix() not in config.files
        ):
            raise ValueError(
                f"Unverified model file in snapshot: {relative.as_posix()}"
            )
    files = {}
    for name, identity in config.files.items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or path == directory:
            raise ValueError("Model file escapes snapshot")
        if path.stat().st_size != identity.size:
            raise ValueError(f"Model size mismatch: {name}")
        digest = file_digest(path)
        if identity.sha256 and digest != identity.sha256:
            raise ValueError(f"Model SHA-256 mismatch: {name}")
        if identity.git_blob_sha1:
            blob = hashlib.sha1(
                f"blob {identity.size}\0".encode() + path.read_bytes()
            ).hexdigest()
            if blob != identity.git_blob_sha1:
                raise ValueError(f"Model git blob mismatch: {name}")
        files[name] = {"bytes": identity.size, "sha256": digest}
    return files


def prepare_model(root: Path, config: ModelConfig):
    from huggingface_hub import snapshot_download

    directory = confined(root, config.local_path, "data/cache")
    snapshot_download(
        config.repository,
        revision=config.revision,
        local_dir=directory,
        allow_patterns=list(config.files),
        max_workers=4,
    )
    files = check_model_files(root, config)
    ledger = {
        "repository": config.repository,
        "revision": config.revision,
        "license": "MIT",
        "source": f"https://huggingface.co/{config.repository}/tree/{config.revision}",
        "local_path": config.local_path,
        "files": files,
        "backend": "sentence-transformers dense-only",
        "dimension": config.dimension,
        "max_sequence_length": config.max_sequence_length,
        "upstream_file_identity": {
            n: i.model_dump(exclude_none=True) for n, i in config.files.items()
        },
    }
    path = confined(root, config.ledger_path, "data/catalog")
    if path.is_symlink() or (path.exists() and path.stat().st_nlink > 1):
        raise ValueError("Model ledger cannot be a linked file")
    write_json(path, ledger)
    return {
        "ledger": config.ledger_path,
        "files": len(files),
        "bytes": sum(f["bytes"] for f in files.values()),
    }


def verified_model(root: Path, config: ModelConfig):
    path = confined(root, config.ledger_path, "data/catalog")
    ledger = json.loads(path.read_text(encoding="utf-8"))
    files = check_model_files(root, config)
    if (
        ledger["repository"],
        ledger["revision"],
        ledger["local_path"],
        ledger["files"],
    ) != (config.repository, config.revision, config.local_path, files):
        raise ValueError("Model ledger identity mismatch")
    return ledger, sha256(path.read_bytes())


def checked_vectors(values, count: int, dimension: int) -> np.ndarray:
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.shape != (count, dimension) or not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding shape or nonfinite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms < 1e-8):
        raise ValueError("Zero embedding vector")
    return vectors / norms[:, None]


class DenseEncoder:
    def __init__(self, root: Path, config: ModelConfig):
        import torch
        from sentence_transformers import SentenceTransformer

        if config.device == "cuda" and not torch.cuda.is_available():
            raise ValueError("Configured CUDA device is unavailable")
        self.config = config
        directory = confined(root, config.local_path, "data/cache")
        self.model = SentenceTransformer(
            str(directory),
            device=config.device,
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={
                "use_safetensors": False,
                "torch_dtype": torch.float16
                if config.precision == "float16"
                else torch.float32,
            },
        )
        if (
            self.model.get_sentence_embedding_dimension() != config.dimension
            or self.model.max_seq_length != config.max_sequence_length
        ):
            raise ValueError("Unexpected model dimension/sequence limit")
        self.tokenizer = self.model.tokenizer
        self.descriptor = {
            "tokenizer_class": type(self.tokenizer).__name__,
            "pooling": self.model[1].get_config_dict(),
            "max_sequence_length": self.model.max_seq_length,
        }

    def lengths(self, texts: list[str]) -> list[int]:
        if any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Empty embedding input")
        lengths = [
            len(ids)
            for ids in self.tokenizer(
                texts, add_special_tokens=True, truncation=False, padding=False
            )["input_ids"]
        ]
        if max(lengths, default=0) > self.config.max_sequence_length:
            raise ValueError(
                "Embedding input exceeds actual model tokenizer limit; rechunk explicitly"
            )
        return lengths

    def encode(self, texts: list[str]) -> np.ndarray:
        self.lengths(texts)
        return checked_vectors(
            self.model.encode(
                texts,
                batch_size=self.config.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            len(texts),
            self.config.dimension,
        )
