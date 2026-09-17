from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.api.app import create_app, load_config
from ican.indexing.inputs import load_chunks
from ican.indexing.model import verified_model
from ican.indexing.pipeline import index_directory, index_identity
from ican.ingestion.pipeline import write_json
from ican.retrieval.schema import SearchResponse

QUERY = "Swin-T 的窗口大小配置是多少？"
PREFIX = "data/raw/repositories/Swin-Transformer/configs/swin/"


def summarize(response):
    return [
        {
            "rank": result.rank,
            "score": result.score,
            "chunk_id": result.chunk_id,
            "source_path": result.source.source_path,
            "source_version": result.source.source_version,
            "location": result.source.location,
        }
        for result in response.results
    ]


def verify(root: Path) -> dict:
    config = load_config(root)
    client = TestClient(create_app(root))
    unrestricted_http = client.post(
        "/v1/evidence/search",
        json={
            "query": QUERY,
            "collection": "swin_v1",
            "filters": {"source_types": ["config"]},
        },
    )
    restricted_http = client.post(
        "/v1/evidence/search",
        json={
            "query": QUERY,
            "collection": "swin_v1",
            "filters": {
                "source_types": ["config"],
                "path_prefixes": [PREFIX],
            },
        },
    )
    if unrestricted_http.status_code != 200 or restricted_http.status_code != 200:
        raise ValueError("Evidence HTTP endpoint did not return 200")
    unrestricted = SearchResponse.model_validate(unrestricted_http.json())
    restricted = SearchResponse.model_validate(restricted_http.json())
    if not unrestricted.results or not restricted.results:
        raise ValueError("Functional evidence query returned no results")
    if not all(
        result.source.source_path.startswith(PREFIX) for result in restricted.results
    ):
        raise ValueError("Source path prefix restriction was not enforced")

    _, ledger_hash = verified_model(root, config.model)
    _, snapshots = load_chunks(root, config)
    directory = index_directory(
        root, config, index_identity(config, snapshots, ledger_hash)
    )
    output = {
        "status": "passed",
        "purpose": "functional evidence retrieval only; no gold accuracy claims",
        "query_kind": "Chinese manually constructed smoke query",
        "collection": "swin_v1",
        "unrestricted": summarize(unrestricted),
        "restricted": summarize(restricted),
        "required_path_prefix": PREFIX,
    }
    write_json(directory / "retrieval_smoke.json", output)
    return {"directory": directory.relative_to(root).as_posix(), "result": output}


if __name__ == "__main__":
    print(json.dumps(verify(ROOT), ensure_ascii=False, indent=2))
