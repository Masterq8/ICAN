from __future__ import annotations

from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException

from ican.agent.schema import AgentRequest, AgentResponse, ToolInputError
from ican.indexing.schema import IndexConfig
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.qa.schema import QARequest, QAResponse
from ican.research.schema import (
    ClaimVerificationRequest,
    ClaimVerificationResponse,
    ExtractionSubmissionRequest,
    ResearchRecord,
    ResearchReport,
    ResearchReportRequest,
    ScreeningSubmissionRequest,
)
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
    agent_service=None,
    research_service=None,
) -> FastAPI:
    app = FastAPI(title="复现有据 Evidence API", version="0.1")
    project_root = (root or ROOT).resolve()
    evidence = service
    qa = qa_service
    agent = agent_service
    research = research_service
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

    def get_agent_service():
        nonlocal agent
        with initialization_lock:
            if agent is None:
                from ican.agent.service import AgentService

                agent = AgentService(
                    project_root, load_config(project_root), get_service()
                )
        return agent

    def get_research_service():
        nonlocal research
        with initialization_lock:
            if research is None:
                from ican.research.service import ResearchService

                research = ResearchService(
                    project_root, load_config(project_root), get_service()
                )
        return research

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

    @app.post("/v1/agent/run", response_model=AgentResponse)
    async def run_agent(request: AgentRequest) -> AgentResponse:
        try:
            return await get_agent_service().run(request)
        except CollectionNotFound:
            raise HTTPException(status_code=422, detail="Unknown collection") from None
        except IndexUnavailable:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from None

    @app.post("/v1/research/verify-claims", response_model=ClaimVerificationResponse)
    def verify_research_claims(request: ClaimVerificationRequest):
        try:
            return get_research_service().verify(request.scope, request.claims)
        except (CollectionNotFound, ToolInputError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from None

    @app.post("/v1/research/screening", response_model=ResearchRecord)
    def submit_research_screening(request: ScreeningSubmissionRequest):
        try:
            return get_research_service().submit_screening(request.scope, request.draft)
        except (CollectionNotFound, ToolInputError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from None

    @app.post("/v1/research/extraction", response_model=ResearchRecord)
    def submit_research_extraction(request: ExtractionSubmissionRequest):
        try:
            return get_research_service().submit_extraction(
                request.scope, request.draft
            )
        except (CollectionNotFound, ToolInputError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable:
            raise HTTPException(
                status_code=503, detail="Evidence index is unavailable"
            ) from None

    @app.post("/v1/research/report", response_model=ResearchReport)
    def build_research_report(request: ResearchReportRequest):
        try:
            return get_research_service().build_report(request)
        except (ToolInputError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app
