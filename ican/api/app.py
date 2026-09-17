from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from ican.indexing.schema import IndexConfig
from ican.retrieval.schema import SearchRequest, SearchResponse
from ican.retrieval.service import (
    CollectionNotFound,
    EvidenceSearchService,
    IndexUnavailable,
)

ROOT = Path(__file__).resolve().parents[2]


def load_config(root: Path) -> IndexConfig:
    path = root / "configs/indexing/v1.json"
    return IndexConfig.model_validate_json(path.read_text(encoding="utf-8"))


def create_app(
    root: Path | None = None, service: EvidenceSearchService | None = None
) -> FastAPI:
    app = FastAPI(title="复现有据 Evidence API", version="0.1")
    project_root = (root or ROOT).resolve()
    evidence = service

    def get_service() -> EvidenceSearchService:
        nonlocal evidence
        if evidence is None:
            evidence = EvidenceSearchService(project_root, load_config(project_root))
        return evidence

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/evidence/search", response_model=SearchResponse)
    def search(request: SearchRequest) -> SearchResponse:
        try:
            return get_service().search(request)
        except CollectionNotFound as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable as error:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from error

    return app
