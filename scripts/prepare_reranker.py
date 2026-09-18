"""Download and verify the pinned, local-only P3 reranker."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.retrieval.reranking import RerankerConfig, prepare_reranker

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-ranges", action="store_true")
    args = parser.parse_args()
    config = RerankerConfig.model_validate_json(
        (ROOT / "configs/reranking/v1.json").read_text(encoding="utf-8")
    )
    ledger = prepare_reranker(ROOT, config, http_ranges=args.http_ranges)
    print(
        json.dumps(
            {
                "repository": ledger["repository"],
                "revision": ledger["revision"],
                "files": len(ledger["files"]),
                "bytes": sum(f["bytes"] for f in ledger["files"].values()),
            }
        )
    )
