"""P2.6 query-only retrieval, explicitly bounded generation, and offline scoring."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.api.app import load_config
from ican.evaluation.report import summarize
from ican.evaluation.runner import generate, retrieve, reuse_retrieval
from ican.retrieval.service import EvidenceSearchService

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["retrieval", "generate", "report"])
    parser.add_argument(
        "--run-dir", type=Path, default=ROOT / "data/processed/evaluation/p26-v1"
    )
    parser.add_argument("--variants", default="adapter,paperqa-default")
    parser.add_argument(
        "--reuse-from",
        type=Path,
        help="Reuse a checked preflight snapshot in a new run directory",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        help="Explicit cumulative generation-call cap for this run",
    )
    args = parser.parse_args()
    from filelock import FileLock

    args.run_dir.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(args.run_dir.parent / f".{args.run_dir.name}.lock", timeout=0):
        if args.action == "retrieval":
            variants = args.variants.split(",")
            if (
                not variants
                or len(variants) != len(set(variants))
                or set(variants) - {"adapter", "paperqa-default"}
            ):
                parser.error("Invalid variants")
            if args.reuse_from:
                reuse_retrieval(ROOT, args.run_dir, args.reuse_from, variants)
            else:
                retrieve(
                    ROOT,
                    args.run_dir,
                    EvidenceSearchService(ROOT, load_config(ROOT)),
                    variants,
                )
        elif args.action == "generate":
            if args.max_calls is None or args.max_calls < 1:
                parser.error("generate requires a positive --max-calls")
            asyncio.run(generate(ROOT, args.run_dir, args.max_calls))
        else:
            summary = summarize(ROOT, args.run_dir)
            print(
                json.dumps(
                    {
                        k: summary[k]
                        for k in [
                            "retrieval",
                            "generation",
                            "started_calls",
                            "incomplete",
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )
