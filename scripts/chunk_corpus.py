from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.chunking.pipeline import build_all
from ican.chunking.schema import ChunkConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild hash-checked, provenance-preserving chunks"
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/chunking/v1.json"
    )
    args = parser.parse_args()
    config = ChunkConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
    print(json.dumps(build_all(ROOT, config), ensure_ascii=False, indent=2))
