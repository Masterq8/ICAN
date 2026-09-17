from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.api.app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Serve the local evidence API with exactly one worker."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    # Qdrant local locks its database directory; do not add workers here.
    uvicorn.run(create_app(ROOT), host=args.host, port=args.port, workers=1)
