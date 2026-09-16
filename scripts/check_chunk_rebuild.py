"""Rebuild verified chunks and compare hashes; eval files are hashed only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.chunking.artifacts import artifact_path
from ican.chunking.pipeline import build_all
from ican.chunking.schema import ChunkConfig
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined, write_json
from scripts.verify_chunks import verify


def check(root: Path, config: ChunkConfig):
    names = [
        "chunks.jsonl",
        "chunk_manifest.json",
        "chunk_report.json",
        "chunk_failures.jsonl",
        "review_samples.md",
        "verification_report.json",
    ]
    outputs = [confined(root, d.output_dir, "data/processed") for d in config.datasets]
    for out in outputs:
        artifact_path(out, "rebuild_verification.json").unlink(missing_ok=True)
    protected = {
        confined(root, p, "data/processed")
        for d in config.datasets
        for p in [
            d.parent_manifest,
            *d.inputs.values(),
            *([d.sources] if d.sources else []),
        ]
    }
    protected.update((root / "data/eval").rglob("*.jsonl"))
    baseline = {
        p.relative_to(root).as_posix(): sha256(p.read_bytes())
        for out in outputs
        for p in [out / n for n in names]
    }
    before = {
        p.relative_to(root).as_posix(): sha256(p.read_bytes())
        for p in sorted(protected)
    }
    build_all(root, config)
    verify(root, config)
    rebuilt = {p: sha256((root / p).read_bytes()) for p in baseline}
    after = {p: sha256((root / p).read_bytes()) for p in before}
    if baseline != rebuilt or before != after:
        raise ValueError("Rebuild differs or changed protected input/evaluation files")
    report = {
        "status": "passed",
        "identical_artifacts": len(baseline),
        "unchanged_inputs_and_eval": len(before),
        "artifact_sha256": rebuilt,
        "protected_sha256": before,
    }
    for out in outputs:
        write_json(artifact_path(out, "rebuild_verification.json"), report)
    return {
        k: v
        for k, v in report.items()
        if k not in {"artifact_sha256", "protected_sha256"}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/chunking/v1.json")
    args = parser.parse_args()
    cfg = ChunkConfig.model_validate_json(
        (ROOT / args.config).read_text(encoding="utf-8")
    )
    print(json.dumps(check(ROOT, cfg), ensure_ascii=False, indent=2))
