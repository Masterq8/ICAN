"""Verify chunks, build manifests, parent snapshots, and frozen split hash."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.chunking.artifacts import artifact_path
from ican.chunking.inputs import load_dataset, read_lines
from ican.chunking.schema import Chunk, ChunkConfig
from ican.chunking.verification import validate_chunks
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined, write_json

FROZEN_SHA256 = "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"


def verify(root: Path, config: ChunkConfig):
    for d in config.datasets:
        out = confined(root, d.output_dir, "data/processed")
        artifact_path(out, "verification_report.json").unlink(missing_ok=True)
    frozen_hash = sha256((root / "data/eval/swin_test.jsonl").read_bytes())
    if frozen_hash != FROZEN_SHA256:
        raise ValueError("Swin frozen evaluation file changed")
    reports = []
    for d in config.datasets:
        out = confined(root, d.output_dir, "data/processed")
        manifest = json.loads((out / "chunk_manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] != "passed" or manifest["config_sha256"] != sha256(
            config.model_dump_json().encode()
        ):
            raise ValueError("Chunk manifest status/config mismatch")
        if (
            manifest["config"] != config.model_dump()
            or manifest["dataset_id"] != d.dataset_id
        ):
            raise ValueError("Manifest dataset/config mismatch")
        if (
            manifest["parent_manifest"] != d.parent_manifest
            or manifest["parent_manifest_sha256"] != d.expected_manifest_sha256
        ):
            raise ValueError("Manifest parent mismatch")
        allowed = [(out / "chunks.jsonl").relative_to(root).as_posix()]
        if manifest["index_allowlist"] != allowed:
            raise ValueError("Unexpected index allowlist")
        for name, expected in manifest["artifacts_sha256"].items():
            if (
                name not in {"chunks.jsonl", "chunk_report.json"}
                or sha256((out / name).read_bytes()) != expected
            ):
                raise ValueError("Chunk artifact hash mismatch")
        if set(manifest["artifacts_sha256"]) != {"chunks.jsonl", "chunk_report.json"}:
            raise ValueError("Missing chunk artifact hash")
        parents, hashes = load_dataset(root, d)
        if manifest["parent_input_sha256"] != hashes:
            raise ValueError("Manifest input hashes mismatch")
        chunks = [Chunk.model_validate(c) for c in read_lines(out / "chunks.jsonl")]
        report = validate_chunks(parents, chunks, config, d.dataset_id)
        build_report = json.loads(
            (out / "chunk_report.json").read_text(encoding="utf-8")
        )
        if build_report["status"] != "passed" or build_report["validation"] != report:
            raise ValueError("Build validation report mismatch")
        report.update(
            dataset_id=d.dataset_id,
            frozen_test_sha256=frozen_hash,
            chunk_manifest_sha256=sha256((out / "chunk_manifest.json").read_bytes()),
        )
        write_json(artifact_path(out, "verification_report.json"), report)
        reports.append(report)
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/chunking/v1.json")
    args = parser.parse_args()
    cfg = ChunkConfig.model_validate_json(
        (ROOT / args.config).read_text(encoding="utf-8")
    )
    print(json.dumps(verify(ROOT, cfg), ensure_ascii=False, indent=2))
