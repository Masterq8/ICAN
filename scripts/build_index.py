from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.indexing.pipeline import build_index
from ican.indexing.schema import IndexConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/indexing/v1.json")
    args = parser.parse_args()
    config = IndexConfig.model_validate_json(
        (ROOT / args.config).read_text(encoding="utf-8")
    )
    print(json.dumps(build_index(ROOT, config), ensure_ascii=False, indent=2))
