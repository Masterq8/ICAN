from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_qa_service import EvidenceService, FakeModel

from ican.api.app import create_app
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.qa.schema import QAConfig
from ican.qa.service import QAService
from ican.retrieval.service import CollectionNotFound, IndexUnavailable


def test_http_qa_uses_real_package_and_preserves_existing_routes():
    evidence = EvidenceService()
    qa = QAService(Path("."), evidence, QAConfig(), FakeModel)
    client = TestClient(create_app(service=evidence, qa_service=qa))
    request = {"query": "window?", "collection": "swin_v1"}
    result = client.post("/v1/qa/answer", json=request)
    assert result.status_code == 200
    assert result.json()["status"] == "answered"
    assert client.post("/v1/evidence/search", json=request).status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/v1/qa/answer", json={**request, "limit": 9}).status_code == 422


@pytest.mark.parametrize(
    "error,status",
    [
        (ModelUnavailable, 503),
        (ModelTimeout, 504),
        (IndexUnavailable, 503),
        (CollectionNotFound, 422),
    ],
)
def test_http_errors_are_mapped_without_sensitive_model_details(error, status):
    class BrokenService:
        async def answer(self, request):
            raise error(
                "Unknown evidence collection"
                if error is CollectionNotFound
                else "SECRET"
            )

    result = TestClient(create_app(qa_service=BrokenService())).post(
        "/v1/qa/answer", json={"query": "q", "collection": "swin_v1"}
    )
    assert result.status_code == status
    assert "SECRET" not in result.text
