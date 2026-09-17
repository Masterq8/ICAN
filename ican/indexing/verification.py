from __future__ import annotations

import json
from collections import Counter
from contextlib import closing
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

from ican.chunking.inputs import read_lines
from ican.ingestion.parsers import sha256

from .model import checked_vectors, file_digest
from .schema import IndexConfig


def verify_store(
    directory: Path, rows: list[dict], vectors: np.ndarray, config: IndexConfig
) -> dict:
    """Open a CLOSED database and compare every payload and vector to originals."""
    expected = {r["id"]: (r, vectors[i]) for i, r in enumerate(rows)}
    counts = Counter(r["collection"] for r in rows)
    seen = set()
    self_queries = []
    with closing(QdrantClient(path=str(directory / "qdrant"))) as client:
        if {c.name for c in client.get_collections().collections} != set(counts):
            raise ValueError("Unexpected Qdrant collections")
        for collection, count in sorted(counts.items()):
            spec = client.get_collection(collection).config.params.vectors
            if (
                spec.size != config.model.dimension
                or spec.distance != models.Distance.COSINE
            ):
                raise ValueError("Collection vector configuration mismatch")
            if client.count(collection, exact=True).count != count:
                raise ValueError("Collection point count mismatch")
            offset = None
            first = None
            while True:
                points, offset = client.scroll(
                    collection,
                    limit=128,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
                for p in points:
                    key = str(p.id)
                    if key not in expected or key in seen:
                        raise ValueError("Unexpected or duplicated persisted point")
                    row, vector = expected[key]
                    if row["collection"] != collection or p.payload != row:
                        raise ValueError("Persisted payload/collection mismatch")
                    stored = np.asarray(p.vector, dtype=np.float32)
                    if (
                        stored.shape != vector.shape
                        or not np.isfinite(stored).all()
                        or not np.allclose(stored, vector, rtol=1e-5, atol=2e-6)
                    ):
                        raise ValueError("Persisted vector mismatch")
                    seen.add(key)
                    if first is None:
                        first = (key, vector)
                if offset is None:
                    break
            # A filtered self-vector query verifies scoring+ID in reopened store;
            # unrestricted rank may tie on repeated original snippets.
            key, vector = first
            found = client.query_points(
                collection,
                query=vector.tolist(),
                query_filter=models.Filter(must=[models.HasIdCondition(has_id=[key])]),
                limit=1,
            ).points
            if len(found) != 1 or str(found[0].id) != key or found[0].score < 0.999:
                raise ValueError("Reopened self-vector query failed")
            self_queries.append(
                {"collection": collection, "id": key, "score": found[0].score}
            )
    if seen != set(expected):
        raise ValueError("Missing persisted points")
    return {
        "status": "passed",
        "points": len(seen),
        "collections": dict(sorted(counts.items())),
        "all_payloads_and_vectors_checked": True,
        "reopened_self_queries": self_queries,
    }


def verify_artifacts(
    directory: Path, rows: list[dict], config: IndexConfig, identity: dict
) -> dict:
    manifest = json.loads(
        (directory / "index_manifest.json").read_text(encoding="utf-8")
    )
    if (
        manifest.get("status") != "passed"
        or manifest["identity"] != identity
        or manifest["config"] != config.model_dump()
    ):
        raise ValueError("Index identity/config mismatch")
    if set(manifest["artifact_sha256"]) != {
        "vectors.npy",
        "points.jsonl",
        "token_report.json",
    }:
        raise ValueError("Index artifact allowlist mismatch")
    for name, digest in manifest["artifact_sha256"].items():
        if file_digest(directory / name) != digest:
            raise ValueError("Index artifact hash mismatch")
    saved_rows = read_lines(directory / "points.jsonl")
    if len(saved_rows) != len(rows):
        raise ValueError("Index mapping size mismatch")
    lengths = []
    for current, saved in zip(rows, saved_rows, strict=True):
        if {k: v for k, v in saved.items() if k != "actual_tokens"} != current:
            raise ValueError("Index mapping/corpus mismatch")
        length = saved["actual_tokens"]
        if (
            not isinstance(length, int)
            or not 0 < length <= config.model.max_sequence_length
        ):
            raise ValueError("Index token count exceeds configured limit")
        lengths.append(length)
    report = json.loads((directory / "token_report.json").read_text(encoding="utf-8"))
    if report["documents"] != len(lengths) or report["max_actual_tokens"] != max(
        lengths
    ):
        raise ValueError("Index token report mismatch")
    vectors = np.load(directory / "vectors.npy", allow_pickle=False)
    normalized = checked_vectors(vectors, len(rows), config.model.dimension)
    if vectors.dtype != np.float32 or not np.allclose(
        vectors, normalized, rtol=1e-5, atol=2e-6
    ):
        raise ValueError("Index vectors must be normalized float32")
    result = verify_store(directory, saved_rows, vectors, config)
    result["manifest_sha256"] = sha256((directory / "index_manifest.json").read_bytes())
    return result
