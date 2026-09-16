"""Download small official transport shards at a pinned revision; select papers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import write_json, write_jsonl
from ican.ingestion.qasper import CARD_REVISION, DATASET_REVISION, convert_papers


def prepare(train_count: int = 20, validation_count: int = 10):
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    raw = ROOT / "data/raw/external/qasper"
    output = ROOT / "data/processed/qasper_external/v1"
    evaluation = ROOT / "data/eval/qasper_external/v1"
    output.mkdir(parents=True, exist_ok=True)
    evaluation.mkdir(parents=True, exist_ok=True)
    selected, transport, counts = {}, [], {}
    for split, count in [("train", train_count), ("validation", validation_count)]:
        path = Path(
            hf_hub_download(
                "allenai/qasper",
                f"qasper/{split}/0000.parquet",
                repo_type="dataset",
                revision=DATASET_REVISION,
                local_dir=raw,
            )
        )
        table = pq.read_table(path)
        # Stable selection uses paper ID, independent of upstream row ordering.
        rows = sorted(table.to_pylist(), key=lambda x: x["id"])[:count]
        if len(rows) != count:
            raise ValueError("Not enough papers for requested sample")
        selected[split] = [row["id"] for row in rows]
        corpus, questions = convert_papers(rows, split)
        write_jsonl(output / f"{split}_corpus.jsonl", corpus)
        write_jsonl(evaluation / f"{split}_questions.jsonl", questions)
        counts[split] = {
            "papers": len(rows),
            "units": len(corpus),
            "questions": len(questions),
            "annotations": sum(len(q["answers"]) for q in questions),
            "unmatched_evidence": sum(
                len(a["unmatched_evidence"]) for q in questions for a in q["answers"]
            ),
            "ambiguous_matches": sum(
                len(a["ambiguous_evidence_matches"])
                for q in questions
                for a in q["answers"]
            ),
        }
        transport.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
        )
    if set(selected["train"]) & set(selected["validation"]):
        raise ValueError("Cross-split paper leakage")
    card = Path(
        hf_hub_download(
            "allenai/qasper",
            "README.md",
            repo_type="dataset",
            revision=CARD_REVISION,
            local_dir=raw / "card",
        )
    )
    manifest = {
        "dataset_id": "qasper_external_v1",
        "source": "https://huggingface.co/datasets/allenai/qasper",
        "dataset_revision": DATASET_REVISION,
        "card_revision": CARD_REVISION,
        "card_sha256": sha256(card.read_bytes()),
        "license": "CC-BY-4.0",
        "selection": "first N paper IDs in lexicographic order within each original split",
        "selected_papers": selected,
        "counts": counts,
        "transport": transport,
        "location": "section/paragraph or caption index; PDF pages unavailable",
        "index_allowlist": [
            f"data/processed/qasper_external/v1/{s}_corpus.jsonl" for s in selected
        ],
        "evaluation_only": [
            f"data/eval/qasper_external/v1/{s}_questions.jsonl" for s in selected
        ],
        "scope": "External benchmark; Swin frozen test remains unchanged; no QASPER test download",
        "artifact_sha256": {
            str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes())
            for folder in (output, evaluation)
            for p in sorted(folder.glob("*.jsonl"))
        },
    }
    write_json(output / "manifest.json", manifest)
    write_json(ROOT / "data/catalog/qasper-external.json", manifest)
    print(counts)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-count", type=int, default=20)
    parser.add_argument("--validation-count", type=int, default=10)
    args = parser.parse_args()
    if args.train_count < 1 or args.validation_count < 1:
        parser.error("Counts must be positive")
    prepare(args.train_count, args.validation_count)
