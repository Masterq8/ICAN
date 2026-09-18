"""Export one sealed P3 ranking into a new, bounded PaperQA2 evaluation run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.data import digest, load_chunk_registry, load_inputs, read_jsonl
from ican.evaluation.runner import append_record, protocol, validate_snapshot
from scripts.evaluate_retrieval_strategies import (
    STRATEGIES,
    run_identity,
    validate_records,
)


def export(root: Path, source: Path, target: Path):
    cases, _, fixed = load_inputs(root)
    initial = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    seal = json.loads((source / "retrieval-seal.json").read_text(encoding="utf-8"))
    if initial["identity"] != run_identity(root, fixed):
        raise ValueError("P3 source/config/input identity changed")
    if seal["sha256"] != digest(source / "retrieval.jsonl"):
        raise ValueError("P3 source snapshot changed")
    records = read_jsonl(source / "retrieval.jsonl")
    validate_records(
        records,
        cases,
        load_chunk_registry(root),
        initial["identity"]["index_fingerprint"],
    )
    if len(records) != len(cases) * len(STRATEGIES):
        raise ValueError("P3 ablation source is incomplete")
    selected = {r["case_key"]: r for r in records if r["strategy"] == "hybrid_rerank"}
    if set(selected) != {c.key for c in cases} or target.exists():
        raise ValueError("Expected complete ranking and a new destination")
    target.mkdir(parents=True)
    path = target / "retrieval.jsonl"
    for case in cases:
        row = selected[case.key]
        append_record(
            path,
            {
                "key": case.key,
                "case": case.record(),
                "response": row["response"],
                "elapsed_seconds": row["elapsed_seconds"],
            },
        )
    manifest = {
        "protocol": protocol(root, ["adapter"]),
        "input_sha256": fixed,
        "cases": [c.record() for c in cases],
        "retrieval_sha256": digest(path),
        "retrieval_provenance": {"p3_identity": initial["identity"], "seal": seal},
        "generation_call_cap": len(cases),
    }
    validate_snapshot(root, target, cases, manifest)
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"cases": len(cases), "variants": ["adapter"], "generation_calls": 0}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    from filelock import FileLock

    args.run_dir.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(args.run_dir.parent / f".{args.run_dir.name}.lock", timeout=0):
        export(ROOT, args.source, args.run_dir)
