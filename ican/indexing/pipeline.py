from __future__ import annotations

import importlib.metadata
import json
import time
import uuid
from collections import Counter
from contextlib import closing
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined, write_json, write_jsonl

from .inputs import load_chunks
from .model import DenseEncoder, checked_vectors, file_digest, verified_model
from .schema import IndexConfig
from .verification import verify_artifacts, verify_store


def index_identity(config: IndexConfig, snapshots: dict, ledger_sha256: str) -> dict:
    return {
        "config_sha256": sha256(config.model_dump_json().encode()),
        "chunk_snapshots": snapshots,
        "model_ledger_sha256": ledger_sha256,
        "libraries": {
            p: importlib.metadata.version(p)
            for p in [
                "torch",
                "transformers",
                "sentence-transformers",
                "qdrant-client",
                "tokenizers",
                "numpy",
            ]
        },
    }


def index_directory(root: Path, config: IndexConfig, identity: dict) -> Path:
    fingerprint = sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    )
    return confined(root, config.storage_root, "data/indexes") / fingerprint


def build_index(
    root: Path,
    config: IndexConfig,
    *,
    rows=None,
    snapshots=None,
    ledger_sha256=None,
    encoder=None,
):
    # Injection is for offline tests; CLI always validates real inputs and model.
    if rows is None:
        rows, snapshots = load_chunks(root, config)
    if ledger_sha256 is None:
        _, ledger_sha256 = verified_model(root, config.model)
    identity = index_identity(config, snapshots, ledger_sha256)
    destination = index_directory(root, config, identity)
    if destination.exists():
        result = verify_artifacts(destination, rows, config, identity)
        return {
            "status": "reused",
            "directory": destination.relative_to(root).as_posix(),
            "verification": result,
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep staging names short on Windows (Qdrant appends collection/db paths).
    staging = destination.parent / f".staging-{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        encoder = encoder or DenseEncoder(root, config.model)
        texts = [row["chunk"]["embedding_text"] for row in rows]
        lengths = encoder.lengths(texts)
        if len(lengths) != len(rows) or any(
            not isinstance(n, int) or not 0 < n <= config.model.max_sequence_length
            for n in lengths
        ):
            raise ValueError("Invalid actual tokenizer lengths")
        saved_rows = [
            {**row, "actual_tokens": n} for row, n in zip(rows, lengths, strict=True)
        ]
        parts = []
        for start in range(0, len(texts), 64):
            part = texts[start : start + 64]
            parts.append(
                checked_vectors(encoder.encode(part), len(part), config.model.dimension)
            )
            if start % 512 == 0:
                print(
                    f"Encoded {min(start + len(part), len(texts))}/{len(texts)} chunks",
                    flush=True,
                )
        vectors = np.concatenate(parts)
        np.save(staging / "vectors.npy", vectors, allow_pickle=False)
        write_jsonl(staging / "points.jsonl", saved_rows)
        counts = Counter(row["collection"] for row in rows)
        token_report = {
            "status": "passed",
            "documents": len(rows),
            "tokenizer": encoder.descriptor,
            "max_actual_tokens": max(lengths),
            "min_actual_tokens": min(lengths),
            "mean_actual_tokens": sum(lengths) / len(lengths),
            "limit": config.model.max_sequence_length,
            "truncated_documents": 0,
            "by_collection": {
                c: {
                    "documents": counts[c],
                    "max_actual_tokens": max(
                        n
                        for row, n in zip(rows, lengths, strict=True)
                        if row["collection"] == c
                    ),
                }
                for c in sorted(counts)
            },
        }
        write_json(staging / "token_report.json", token_report)
        with closing(QdrantClient(path=str(staging / "qdrant"))) as client:
            for collection in sorted(counts):
                client.create_collection(
                    collection,
                    vectors_config=models.VectorParams(
                        size=config.model.dimension, distance=models.Distance.COSINE
                    ),
                )
            for start in range(0, len(rows), 64):
                grouped = {}
                for i in range(start, min(start + 64, len(rows))):
                    row = saved_rows[i]
                    grouped.setdefault(row["collection"], []).append(
                        models.PointStruct(
                            id=row["id"], vector=vectors[i].tolist(), payload=row
                        )
                    )
                for collection, points in grouped.items():
                    client.upsert(collection, points=points, wait=True)
        reopened = verify_store(staging, saved_rows, vectors, config)
        manifest = {
            "status": "passed",
            "schema_version": config.schema_version,
            "identity": identity,
            "config": config.model_dump(),
            "encoder": encoder.descriptor,
            "dimension": config.model.dimension,
            "distance": config.distance,
            "vector_dtype": "float32",
            "normalized": True,
            "collections": dict(sorted(counts.items())),
            "qdrant_path": "qdrant",
            "artifact_sha256": {
                n: file_digest(staging / n)
                for n in ["vectors.npy", "points.jsonl", "token_report.json"]
            },
        }
        write_json(staging / "index_manifest.json", manifest)
        result = verify_artifacts(staging, rows, config, identity)
        write_json(staging / "verification_report.json", result)
        report = {
            "status": "passed",
            "seconds": time.perf_counter() - started,
            "collections": dict(sorted(counts.items())),
            "points": len(rows),
            "max_actual_tokens": max(lengths),
            "reopen_verification": reopened,
        }
        if config.model.device == "cuda":
            import torch

            report["gpu"] = torch.cuda.get_device_name(0)
            report["gpu_peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 2**20
            report["gpu_peak_reserved_mib"] = torch.cuda.max_memory_reserved() / 2**20
        write_json(staging / "build_report.json", report)
        # Destination never existed: no successful version is deleted/overwritten.
        staging.rename(destination)
        return {
            "status": "built",
            "directory": destination.relative_to(root).as_posix(),
            "report": report,
        }
    except Exception as error:
        (staging / "index_manifest.json").unlink(missing_ok=True)
        (staging / "verification_report.json").unlink(missing_ok=True)
        write_json(
            staging / "build_report.json",
            {"status": "failed", "error": f"{type(error).__name__}: {error}"},
        )
        raise
