from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.ingestion.pipeline import ingest
from ican.ingestion.schema import IngestionConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild version-checked Swin parsing artifacts"
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/ingestion/swin-v1.json"
    )
    parser.add_argument("--backend", choices=["docling", "pymupdf"])
    args = parser.parse_args()
    config = IngestionConfig.model_validate_json(
        args.config.read_text(encoding="utf-8")
    )
    if args.backend:
        config.pdf_backend = args.backend
    report = ingest(ROOT, config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)
