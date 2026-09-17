from __future__ import annotations

import json
import uuid
from pathlib import Path

from ican.chunking.inputs import load_dataset, read_lines
from ican.chunking.schema import Chunk, ChunkConfig
from ican.chunking.verification import validate_chunks
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined

from .schema import IndexConfig

FROZEN_SHA256 = "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"


def point_id(collection: str, chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ican:{collection}:{chunk_id}"))


def load_chunks(root: Path, config: IndexConfig) -> tuple[list[dict], dict]:
    # Hash-only integrity checks. These files never become encoder/index inputs.
    for relative, expected in config.evaluation_sha256.items():
        path = confined(root, relative, "data/eval")
        if sha256(path.read_bytes()) != expected:
            raise ValueError(f"Evaluation snapshot hash mismatch: {relative}")
    if sha256((root / "data/eval/swin_test.jsonl").read_bytes()) != FROZEN_SHA256:
        raise ValueError("Frozen evaluation file changed")
    cfg_path = confined(root, config.chunk_config, "configs")
    chunk_config = ChunkConfig.model_validate_json(cfg_path.read_text(encoding="utf-8"))
    datasets = {d.dataset_id: d for d in chunk_config.datasets}
    rows, snapshots = [], {}
    for source in config.sources:
        if source.dataset_id not in datasets:
            raise ValueError("Unknown chunk dataset")
        dataset = datasets[source.dataset_id]
        directory = confined(root, source.directory, "data/processed")
        if directory != confined(root, dataset.output_dir, "data/processed"):
            raise ValueError("Chunk source directory mismatch")
        path = directory / "chunk_manifest.json"
        if sha256(path.read_bytes()) != source.expected_manifest_sha256:
            raise ValueError("Chunk manifest hash mismatch")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        expected_allowed = [(directory / "chunks.jsonl").relative_to(root).as_posix()]
        if (
            manifest["status"] != "passed"
            or manifest["dataset_id"] != source.dataset_id
            or manifest["index_allowlist"] != expected_allowed
        ):
            raise ValueError("Invalid chunk manifest/allowlist")
        if manifest["config"] != chunk_config.model_dump() or manifest[
            "config_sha256"
        ] != sha256(chunk_config.model_dump_json().encode()):
            raise ValueError("Chunk configuration mismatch")
        if (
            manifest["parent_manifest"] != dataset.parent_manifest
            or manifest["parent_manifest_sha256"] != dataset.expected_manifest_sha256
        ):
            raise ValueError("Chunk parent manifest mismatch")
        if set(manifest["artifacts_sha256"]) != {"chunks.jsonl", "chunk_report.json"}:
            raise ValueError("Invalid chunk artifacts")
        for name, digest in manifest["artifacts_sha256"].items():
            if sha256((directory / name).read_bytes()) != digest:
                raise ValueError("Chunk artifact hash mismatch")
        parents, parent_hashes = load_dataset(root, dataset)
        if parent_hashes != manifest["parent_input_sha256"]:
            raise ValueError("Chunk parent hash mismatch")
        chunks = [
            Chunk.model_validate(c) for c in read_lines(directory / "chunks.jsonl")
        ]
        result = validate_chunks(parents, chunks, chunk_config, source.dataset_id)
        verified = json.loads(
            (directory / "verification_report.json").read_text(encoding="utf-8")
        )
        if (
            any(verified.get(k) != v for k, v in result.items())
            or verified.get("chunk_manifest_sha256") != source.expected_manifest_sha256
            or verified.get("frozen_test_sha256") != FROZEN_SHA256
        ):
            raise ValueError("Chunk verification report mismatch")
        if set(source.collections) != {c.split for c in chunks}:
            raise ValueError("Configured collections do not cover exact corpus splits")
        for c in chunks:
            collection = source.collections[c.split]
            rows.append(
                {
                    "id": point_id(collection, c.chunk_id),
                    "collection": collection,
                    "chunk": c.model_dump(),
                    "embedding_input_sha256": sha256(c.embedding_text.encode()),
                }
            )
        snapshots[source.dataset_id] = {
            "chunk_manifest_sha256": source.expected_manifest_sha256,
            "chunk_artifacts_sha256": manifest["artifacts_sha256"],
            "parent_input_sha256": parent_hashes,
            "parent_manifest_sha256": dataset.expected_manifest_sha256,
            "verification_sha256": sha256(
                (directory / "verification_report.json").read_bytes()
            ),
        }
    rows.sort(key=lambda row: (row["collection"], row["chunk"]["chunk_id"]))
    if len({r["id"] for r in rows}) != len(rows) or not rows:
        raise ValueError("Duplicate/empty points")
    return rows, snapshots
