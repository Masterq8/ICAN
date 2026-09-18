"""Create offline answer review packets from the completed, sealed P3 QA run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.data import digest, load_inputs, read_jsonl
from ican.evaluation.runner import validate_snapshot
from scripts.finalize_baseline_audit import validate_completed_run


def main():
    run = ROOT / "data/processed/evaluation/p3-qa-v1"
    cases, gold, fixed = load_inputs(ROOT)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["input_sha256"] != fixed:
        raise ValueError("Review references changed")
    validate_snapshot(ROOT, run, cases, manifest)
    completed = validate_completed_run(
        read_jsonl(run / "journal.jsonl"), {c.key + "/adapter" for c in cases}
    )
    groups = {"root": [], "validation": []}
    for case in cases:
        record = completed[case.key + "/adapter"]
        groups["validation" if case.split == "validation" else "root"].append(
            {
                "case": case.record(),
                "gold": gold[case.key],
                "answer": record,
            }
        )
    for group, rows in groups.items():
        path = run / f"{group}-review-packet.jsonl"
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "journal_sha256": digest(run / "journal.jsonl"),
                "packet_n": {k: len(v) for k, v in groups.items()},
                "generation_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
