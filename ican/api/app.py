from __future__ import annotations

from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException

from ican.indexing.schema import IndexConfig
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.qa.schema import QARequest, QAResponse
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
    root: Path | None = None,
    service: EvidenceSearchService | None = None,
    qa_service=None,
) -> FastAPI:
    app = FastAPI(title="复现有据 Evidence API", version="0.1")
    project_root = (root or ROOT).resolve()
    evidence = service
    qa = qa_service
    initialization_lock = RLock()

    def get_service() -> EvidenceSearchService:
        nonlocal evidence
        with initialization_lock:
            if evidence is None:
                from ican.retrieval.hybrid import HybridEvidenceSearchService

                evidence = HybridEvidenceSearchService(
                    project_root, load_config(project_root)
                )
        return evidence

    def get_qa_service():
        nonlocal qa
        with initialization_lock:
            if qa is None:
                from ican.qa.service import QAService

                qa = QAService(project_root, get_service())
        return qa

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

    @app.post("/v1/qa/answer", response_model=QAResponse)
    async def answer(request: QARequest) -> QAResponse:
        try:
            return await get_qa_service().answer(request)
        except CollectionNotFound as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from None
        except ModelUnavailable:
            raise HTTPException(
                status_code=503, detail="Generation service is unavailable"
            ) from None
        except ModelTimeout:
            raise HTTPException(
                status_code=504, detail="Generation timed out"
            ) from None

    return app
