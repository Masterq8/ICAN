"""Exercise the real P3 HTTP routes with local models; no generation calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from ican.api.app import create_app, load_config
from ican.retrieval.hybrid import HybridEvidenceSearchService
from ican.retrieval.scope import path_family


def main():
    service = HybridEvidenceSearchService(ROOT, load_config(ROOT))
    checks = []
    with TestClient(create_app(ROOT, service=service)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert service.reranker is None and service.dense.encoder is None
        for label, query, family, filters in [
            (
                "configuration_chain",
                "使用swin_tiny_patch4_window7_224.yaml，MODEL.DROP_PATH_RATE配置链是什么？",
                "auto",
                {},
            ),
            (
                "explicit_v2",
                "Swin V2的PatchEmbed如何实现？",
                "swin_v2",
                {
                    "source_types": ["code"],
                    "path_prefixes": [
                        "data/raw/repositories/Swin-Transformer/models/swin_transformer_v2.py"
                    ],
                },
            ),
        ]:
            response = client.post(
                "/v1/evidence/search",
                json={
                    "query": query,
                    "collection": "swin_v1",
                    "strategy": "hybrid_rerank",
                    "family": family,
                    "filters": filters,
                    "limit": 8,
                },
            )
            assert response.status_code == 200, response.json()
            data = response.json()
            assert data["trace"]["strategy"] == "hybrid_rerank"
            assert (
                data["trace"]["reranker"]["revision"]
                == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
            )
            assert data["results"] and len(data["results"]) <= 8
            if label == "explicit_v2":
                assert all(
                    path_family(r["source"]["source_path"]) == "swin_v2"
                    for r in data["results"]
                )
            else:
                config = [
                    r for r in data["results"] if r["source"]["source_type"] == "config"
                ]
                assert config and all(
                    r["source"]["source_path"].endswith(
                        "/swin_tiny_patch4_window7_224.yaml"
                    )
                    for r in config
                )
                assert any("merge_from_file" in r["text"] for r in data["results"])
                assert any("merge_from_list" in r["text"] for r in data["results"])
            checks.append({"check": label, "response": data})
    destination = ROOT / "data/processed/evaluation/p3-api-smoke.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"generation_calls": 0, "checks": checks}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    print(
        json.dumps({"checks": len(checks), "generation_calls": 0, "status": "passed"})
    )


if __name__ == "__main__":
    main()
