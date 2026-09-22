import pytest
from fastapi.testclient import TestClient

from ican.agent.schema import AgentResponse, BudgetExhausted
from ican.api.app import create_app
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.retrieval.service import CollectionNotFound


class FakeAgent:
    def __init__(self):
        self.request = None

    async def run(self, request):
        self.request = request
        return AgentResponse(
            task_id="abc",
            status="budget_exhausted",
            stop_reason="test_budget",
            planner_model="deepseek-v4-pro",
            answer_model="deepseek-flash",
        )


def test_override_inputs_are_bounded_before_any_paid_planning(tmp_path):
    client = TestClient(create_app(root=tmp_path, agent_service=FakeAgent()))
    for overrides in [
        {"opts": ["MODEL.DROP_PATH_RATE"]},
        {"opts": ["MODEL.DROP_PATH_RATE", "x" * 1025]},
        {"cli": {"batch_size": {"nested": "value"}}},
        {"cli": {"batch_size": 10**100}},
    ]:
        result = client.post(
            "/v1/agent/run",
            json={"query": "q", "collection": "swin_v1", "user_overrides": overrides},
        )
        assert result.status_code == 422


def test_lazy_health_and_agent_http_contract(tmp_path):
    assert TestClient(create_app(root=tmp_path)).get("/health").json() == {
        "status": "ok"
    }
    agent = FakeAgent()
    client = TestClient(create_app(root=tmp_path, agent_service=agent))
    result = client.post(
        "/v1/agent/run",
        json={
            "query": "Swin-T",
            "collection": "swin_v1",
            "family": "swin_v1",
            "filters": {"source_types": ["code"]},
        },
    )
    assert result.status_code == 200
    assert result.json()["status"] == "budget_exhausted"
    assert agent.request.family == "swin_v1" and agent.request.filters.source_types == [
        "code"
    ]
    assert "api_key" not in str(result.json())


def test_unknown_collection_and_invalid_paths_return_422(tmp_path):
    class Absent:
        async def run(self, request):
            raise CollectionNotFound("absent")

    client = TestClient(create_app(root=tmp_path, agent_service=Absent()))
    assert (
        client.post(
            "/v1/agent/run", json={"query": "q", "collection": "unknown"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/agent/run",
            json={
                "query": "q",
                "collection": "swin_v1",
                "filters": {"path_prefixes": ["../.env"]},
            },
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (BudgetExhausted("limit"), 429),
        (ModelUnavailable("missing"), 503),
        (ModelTimeout("timeout"), 504),
    ],
)
def test_agent_provider_failures_have_explicit_http_status(tmp_path, error, status):
    class Failing:
        async def run(self, request):
            raise error

    client = TestClient(create_app(root=tmp_path, agent_service=Failing()))
    response = client.post(
        "/v1/agent/run", json={"query": "q", "collection": "swin_v1"}
    )
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]
