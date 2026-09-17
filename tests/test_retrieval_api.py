from __future__ import annotations

from fastapi.testclient import TestClient

from ican.api.app import create_app
from ican.retrieval.schema import SearchRequest, SearchResponse
from ican.retrieval.service import CollectionNotFound, IndexUnavailable


class FakeEvidenceService:
    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse.model_validate(
            {
                "index_fingerprint": "a" * 64,
                "collection": request.collection,
                "query": request.query,
                "filters": request.filters,
                "results": [
                    {
                        "rank": 1,
                        "score": 0.9,
                        "chunk_id": "chunk-1",
                        "text": "WINDOW_SIZE: 7",
                        "review_required": False,
                        "source": {
                            "source_id": "source-1",
                            "source_type": "config",
                            "source_path": "configs/swin/swin_tiny.yaml",
                            "source_version": "commit-1",
                            "location": {"line_start": 1, "line_end": 2},
                        },
                    }
                ],
            }
        )


class UnavailableEvidenceService:
    def search(self, request: SearchRequest) -> SearchResponse:
        raise IndexUnavailable("local error detail must not be exposed")


class UnknownCollectionEvidenceService:
    def search(self, request: SearchRequest) -> SearchResponse:
        raise CollectionNotFound("Unknown evidence collection")


def test_health_does_not_require_evidence_service():
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_route_returns_evidence_only():
    response = TestClient(create_app(service=FakeEvidenceService())).post(
        "/v1/evidence/search", json={"query": "window", "collection": "swin_v1"}
    )

    assert response.status_code == 200
    assert set(response.json()["results"][0]) == {
        "rank",
        "score",
        "chunk_id",
        "text",
        "review_required",
        "source",
    }


def test_search_route_maps_unavailable_index_to_503_without_internal_detail():
    response = TestClient(create_app(service=UnavailableEvidenceService())).post(
        "/v1/evidence/search", json={"query": "x", "collection": "swin_v1"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Evidence index is unavailable"}


def test_search_route_maps_unknown_collection_to_422():
    response = TestClient(create_app(service=UnknownCollectionEvidenceService())).post(
        "/v1/evidence/search", json={"query": "x", "collection": "not_real"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown evidence collection"}


def test_search_route_returns_422_for_invalid_request():
    response = TestClient(create_app(service=FakeEvidenceService())).post(
        "/v1/evidence/search", json={"query": " ", "collection": "swin_v1"}
    )

    assert response.status_code == 422
