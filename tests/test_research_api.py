from fastapi.testclient import TestClient

from ican.agent.schema import AgentRequest
from ican.api.app import create_app
from ican.research.schema import ClaimVerificationResponse, ResearchReport


class FakeResearch:
    def __init__(self):
        self.scope = None

    def verify(self, scope, claims):
        self.scope = scope
        return ClaimVerificationResponse(verdicts=[])

    def submit_screening(self, scope, draft):
        raise AssertionError("not used by this test")

    def submit_extraction(self, scope, draft):
        raise AssertionError("not used by this test")

    def build_report(self, request):
        return ResearchReport(record_ids=request.record_ids, markdown="# report")


def test_research_claim_endpoint_is_lazy_and_forwards_the_fixed_scope(tmp_path):
    research = FakeResearch()
    app = create_app(root=tmp_path, research_service=research)
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post(
        "/v1/research/verify-claims",
        json={
            "scope": {
                "query": "Swin merge",
                "collection": "swin_v1",
                "family": "swin_v1",
            },
            "claims": [
                {
                    "statement": "A conclusion needs human review.",
                    "kind": "inference",
                    "evidence_ids": ["chunk-id"],
                }
            ],
        },
    )
    assert response.status_code == 200 and response.json() == {"verdicts": []}
    assert isinstance(research.scope, AgentRequest)
    assert research.scope.family == "swin_v1"


def test_research_api_rejects_invalid_scope_and_path_like_record_ids(tmp_path):
    client = TestClient(create_app(root=tmp_path, research_service=FakeResearch()))
    assert (
        client.post(
            "/v1/research/verify-claims",
            json={
                "scope": {
                    "query": "q",
                    "collection": "swin_v1",
                    "filters": {"path_prefixes": ["../.env"]},
                },
                "claims": [
                    {"statement": "x", "kind": "inference", "evidence_ids": ["a"]}
                ],
            },
        ).status_code
        == 422
    )
    assert (
        client.post("/v1/research/report", json={"record_ids": ["../.env"]}).status_code
        == 422
    )
