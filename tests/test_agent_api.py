import pytest
from fastapi.testclient import TestClient

from ican.agent.public_response import to_public_agent_response
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


def test_agent_http_exposes_only_safe_ordered_trajectory(tmp_path):
    class TracedAgent:
        async def run(self, request):
            return AgentResponse(
                task_id="task-safe",
                status="completed",
                stop_reason="final_answer_generated",
                planner_model="deepseek-v4-pro",
                answer_model="deepseek-flash",
                trajectory=[
                    {
                        "event": "planner",
                        "turn": 1,
                        "action": {
                            "content": "PRIVATE_PLANNER_TEXT",
                            "tool_calls": [],
                        },
                    },
                    {
                        "event": "tool",
                        "turn": 1,
                        "name": "search_evidence",
                        "arguments": {
                            "query": "Swin PatchEmbed LayerNorm",
                            "source_types": ["paper", "code"],
                            "strategy": "hybrid_rerank",
                            "api_key": "PRIVATE_ARGUMENT",
                        },
                        "tool_call_id": "PRIVATE_CALL_ID",
                        "result": '{"evidence":[{"text":"PRIVATE_RAW_EVIDENCE"}]}',
                        "cached": False,
                    },
                    {
                        "event": "tool",
                        "turn": 1,
                        "name": "gen_answer",
                        "arguments": {"evidence_ids": ["chunk:1"]},
                        "tool_call_id": "PRIVATE_ANSWER_CALL_ID",
                        "result": '{"status":"answered","answer":"PRIVATE_RAW_TOOL_ANSWER"}',
                        "cached": False,
                    },
                ],
            )

    client = TestClient(create_app(root=tmp_path, agent_service=TracedAgent()))
    result = client.post(
        "/v1/agent/run", json={"query": "LayerNorm", "collection": "swin_v1"}
    )

    assert result.status_code == 200
    payload = result.json()
    assert [event["event"] for event in payload["trajectory"]] == [
        "planning",
        "tool",
        "tool",
    ]
    assert [event.get("tool") for event in payload["trajectory"][1:]] == [
        "search_evidence",
        "gen_answer",
    ]
    assert payload["trajectory"][1]["status"] == "completed"
    assert payload["trajectory"][1]["result_summary"] == "检索到 1 项证据"
    serialized = str(payload)
    for sentinel in (
        "PRIVATE_PLANNER_TEXT",
        "PRIVATE_ARGUMENT",
        "PRIVATE_CALL_ID",
        "PRIVATE_RAW_EVIDENCE",
        "PRIVATE_RAW_TOOL_ANSWER",
    ):
        assert sentinel not in serialized


def test_agent_http_projects_only_public_claim_artifacts(tmp_path):
    class ArtifactAgent:
        async def run(self, request):
            return AgentResponse(
                task_id="task-artifacts",
                status="completed",
                stop_reason="final_answer_generated",
                planner_model="deepseek-v4-pro",
                answer_model="deepseek-flash",
                artifacts=[
                    {
                        "kind": "claim_verification",
                        "chunk_ids": ["chunk:1"],
                        "verdicts": [
                            {
                                "status": "supported",
                                "claim": {
                                    "statement": "PatchEmbed uses LayerNorm.",
                                    "kind": "verbatim",
                                    "evidence_ids": ["chunk:1"],
                                    "quote": "PRIVATE_CLAIM_QUOTE",
                                    "conditions": [{"bindings": {"H": 8}}],
                                    "calculation": {"expression": "PRIVATE_CALCULATION"},
                                },
                                "evidence": [
                                    {
                                        "rank": 1,
                                        "score": 0.9,
                                        "chunk_id": "chunk:1",
                                        "text": "Original source excerpt.",
                                        "review_required": False,
                                        "source": {
                                            "source_id": "src:swin",
                                            "source_type": "code",
                                            "source_path": "models/swin_transformer.py",
                                            "source_version": "abc123",
                                            "location": {"line_start": 18, "line_end": 21},
                                        },
                                    }
                                ],
                                "conditions": [{"diagnostic": "PRIVATE_CONDITION_DETAIL"}],
                                "calculation": {"expression": "PRIVATE_VERDICT_CALCULATION"},
                                "diagnostics": ["PRIVATE_DIAGNOSTIC"],
                            }
                        ],
                    },
                    {"kind": "research_report", "markdown": "PRIVATE_REPORT_BODY"},
                    {"kind": "extraction_record", "record": {"value": "PRIVATE_RECORD"}},
                    {"kind": "configuration_trace", "result": "PRIVATE_CONFIG_RESULT"},
                ],
            )

    client = TestClient(create_app(root=tmp_path, agent_service=ArtifactAgent()))
    result = client.post(
        "/v1/agent/run", json={"query": "LayerNorm", "collection": "swin_v1"}
    )

    assert result.status_code == 200
    payload = result.json()
    assert [artifact["kind"] for artifact in payload["artifacts"]] == [
        "claim_verification"
    ]
    verdict = payload["artifacts"][0]["verdicts"][0]
    assert verdict["claim"] == {
        "statement": "PatchEmbed uses LayerNorm.",
        "kind": "verbatim",
        "evidence_ids": ["chunk:1"],
    }
    assert verdict["evidence"][0]["text"] == "Original source excerpt."
    serialized = result.text
    for sentinel in (
        "PRIVATE_CLAIM_QUOTE",
        "PRIVATE_CALCULATION",
        "PRIVATE_VERDICT_CALCULATION",
        "PRIVATE_CONDITION_DETAIL",
        "PRIVATE_DIAGNOSTIC",
        "PRIVATE_REPORT_BODY",
        "PRIVATE_RECORD",
        "PRIVATE_CONFIG_RESULT",
    ):
        assert sentinel not in serialized


@pytest.mark.parametrize(
    ("event", "expected_status", "expected_summary"),
    [
        (
            {
                "event": "tool",
                "turn": 1,
                "name": "search_evidence",
                "arguments": {"query": "find paper"},
                "result": '{"evidence":[{},{}]}',
                "cached": False,
            },
            "completed",
            "检索到 2 项证据",
        ),
        (
            {
                "event": "tool",
                "turn": 1,
                "name": "read_evidence",
                "arguments": {"structure": "PatchEmbed.forward"},
                "result": '{"evidence":[{}]}',
                "cached": True,
            },
            "cached",
            "读取到 1 项证据",
        ),
        (
            {
                "event": "tool",
                "turn": 1,
                "name": "trace_config",
                "arguments": {"field": "MODEL.PATCH_NORM"},
                "result": '{"error":"PRIVATE_VALIDATION_DETAIL"}',
                "cached": False,
            },
            "failed",
            "工具未能完成",
        ),
        (
            {
                "event": "tool",
                "turn": 1,
                "name": "calculate",
                "arguments": {"expression": "2 + 2"},
                "result": "PRIVATE_MALFORMED_RESULT",
                "cached": False,
            },
            "completed",
            "工具已返回结果",
        ),
    ],
)
def test_public_agent_trajectory_summarizes_known_tool_outcomes(
    tmp_path, event, expected_status, expected_summary
):
    response = AgentResponse(
        task_id="task-summary",
        status="completed",
        stop_reason="final_answer_generated",
        planner_model="deepseek-v4-pro",
        answer_model="deepseek-flash",
        trajectory=[event],
    )

    public = to_public_agent_response(response)

    assert public.trajectory[0].status == expected_status
    assert public.trajectory[0].result_summary == expected_summary
    assert "PRIVATE" not in public.model_dump_json()


def test_public_agent_trajectory_bounds_arguments_and_hides_unknown_tools():
    response = AgentResponse(
        task_id="task-bounded",
        status="failed",
        stop_reason="tool_failure",
        planner_model="deepseek-v4-pro",
        answer_model="deepseek-flash",
        trajectory=[
            {
                "event": "tool",
                "turn": 1,
                "name": "search_evidence",
                "arguments": {"query": "q" * 400, "api_key": "PRIVATE"},
                "result": '{"evidence":[]}',
                "cached": False,
            },
            {
                "event": "tool",
                "turn": 2,
                "name": "shell",
                "arguments": {"cmd": "PRIVATE"},
                "result": "PRIVATE",
                "cached": False,
            },
        ],
    )

    public = to_public_agent_response(response)

    assert len(public.trajectory[0].parameter_summary) <= 240
    assert public.trajectory[1].tool == "unknown_tool"
    assert public.trajectory[1].parameter_summary == "参数已按安全规则省略"
    assert "PRIVATE" not in public.model_dump_json()


def test_public_agent_trajectory_supports_legacy_events_without_tool_turns():
    response = AgentResponse(
        task_id="task-legacy",
        status="completed",
        stop_reason="final_answer_generated",
        planner_model="deepseek-v4-pro",
        answer_model="deepseek-flash",
        trajectory=[
            {"event": "planner", "turn": 1, "action": {"content": "private"}},
            {
                "event": "tool",
                "name": "search_evidence",
                "result": '{"evidence":[{}]}',
                "cached": False,
            },
        ],
    )

    public = to_public_agent_response(response)

    assert public.trajectory[1].turn == 1
    assert public.trajectory[1].parameter_summary == ""
    assert "private" not in public.model_dump_json()


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
