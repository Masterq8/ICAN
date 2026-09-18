import hashlib
import json
import re

import pytest
import test_agent_service as fixtures
from test_agent_service import SEARCH, FakeRuntime, action, service

from ican.agent.schema import AgentConfig, AgentRequest, ToolInputError

INFERENCE = {
    "statement": "The authors may have chosen this formula for scalability.",
    "kind": "inference",
    "evidence_ids": ["lr"],
}
SUBMIT = action("submit_claims", {"evidence_ids": ["lr"], "claims": [INFERENCE]})


class WorkflowRuntime(FakeRuntime):
    async def request(self, role, messages, tools=None):
        self.record(role)
        context = messages[1]["content"]
        assert '"kind": "claim_verification"' in context
        assert '"status": "requires_review"' in context
        cid = re.search(r"pqac-[0-9a-f]{8}", context)[0]
        return {
            "role": "assistant",
            "content": f"实现公式可定位，但作者动机需复核 ({cid})。",
        }


def verified_agent(tmp_path, actions, max_paid=8, runtime_class=WorkflowRuntime):
    config = AgentConfig(
        version="p4-agent-v2", workflow_mode="verified", max_planner_calls=3
    )
    agent, _ = service(tmp_path, actions, config, max_paid=max_paid)
    agent.runtime_factory = lambda root, cfg, journal, task_id: runtime_class(
        root, cfg, journal, task_id, actions
    )
    return agent


def test_submission_requires_selected_evidence_and_required_types():
    from ican.agent.workflow import AnswerSubmission

    draft = AnswerSubmission(evidence_ids=["lr"], claims=[INFERENCE])
    draft.validate_selection({"lr"}, ["inference"])
    with pytest.raises(ToolInputError, match="required claim"):
        draft.validate_selection({"lr"}, ["code_execution"])
    with pytest.raises(ToolInputError, match="retained"):
        draft.validate_selection(set(), [])
    with pytest.raises(ToolInputError, match="selected"):
        AnswerSubmission(evidence_ids=["other"], claims=[INFERENCE]).validate_selection(
            {"lr", "other"}, []
        )


def test_advertised_schema_rejects_kind_mismatch_and_requires_payload():
    from jsonschema import ValidationError, validate

    from ican.agent.workflow import submission_tool_schema

    schema = submission_tool_schema()
    valid = {"evidence_ids": ["lr"], "claims": [INFERENCE]}
    validate(valid, schema)
    with pytest.raises(ValidationError):
        validate(
            {"evidence_ids": ["lr"], "claims": [dict(INFERENCE, quote="a quote")]},
            schema,
        )
    for kind in ("verbatim", "numeric", "code_execution"):
        with pytest.raises(ValidationError):
            validate(
                {"evidence_ids": ["lr"], "claims": [dict(INFERENCE, kind=kind)]},
                schema,
            )


@pytest.mark.asyncio
async def test_verified_mode_verifies_before_answer_and_propagates_review(tmp_path):
    agent = verified_agent(tmp_path, [SEARCH, SUBMIT])
    request = AgentRequest(
        query="author motivation",
        collection="swin_v1",
        required_claim_kinds=["inference"],
    )
    result = await agent.run(request)
    assert result.status == "review_required"
    assert result.answer.status == "review_required"
    assert result.usage.planner_calls == 2 and result.usage.answer_calls == 1
    assert result.artifacts[0]["verdicts"][0]["status"] == "requires_review"
    assert [stage["stage"] for stage in result.workflow_stages] == [
        "draft",
        "verify",
        "answer",
    ]
    assert result.workflow_stages[-1]["status"] == "review_required"


@pytest.mark.asyncio
async def test_direct_answer_cannot_bypass_verification(tmp_path):
    direct = action("gen_answer", {"evidence_ids": ["lr"]})
    agent = verified_agent(tmp_path, [SEARCH, direct, direct])
    result = await agent.run(AgentRequest(query="q", collection="swin_v1"))
    assert result.answer is None and result.usage.answer_calls == 0
    assert result.artifacts == []


@pytest.mark.asyncio
async def test_missing_required_type_is_rejected_before_paid_answer(tmp_path):
    agent = verified_agent(tmp_path, [SEARCH, SUBMIT, SUBMIT])
    request = AgentRequest(
        query="code execution",
        collection="swin_v1",
        required_claim_kinds=["code_execution"],
    )
    result = await agent.run(request)
    assert result.answer is None and result.usage.answer_calls == 0
    assert result.artifacts == []
    assert "required claim" in result.trajectory[-1]["result"]


@pytest.mark.asyncio
async def test_verified_answer_respects_paid_cap_without_retry(tmp_path):
    agent = verified_agent(tmp_path, [SEARCH, SUBMIT], max_paid=2)
    result = await agent.run(AgentRequest(query="q", collection="swin_v1"))
    assert result.status == "budget_exhausted"
    assert result.answer is None and result.usage.paid_calls == 2


def test_single_tool_choice_names_function_explicitly():
    from ican.agent.runtime import tool_options

    tools = [{"type": "function", "function": {"name": "submit_claims"}}]
    options = tool_options(tools)
    assert options["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_claims"},
    }
    assert json.dumps(options) and tool_options(None) == {}


@pytest.mark.asyncio
async def test_final_turn_is_submission_only_even_without_evidence(tmp_path):
    calculation = action("calculate", {"expression": "1+1", "evidence_ids": []})
    batch = {
        "role": "assistant",
        "tool_calls": [
            SEARCH["tool_calls"][0],
            dict(SUBMIT["tool_calls"][0], id="submission"),
        ],
    }
    agent = verified_agent(tmp_path, [calculation, calculation, batch])
    runtimes = []

    def factory(root, config, journal, task_id):
        runtime = WorkflowRuntime(
            root, config, journal, task_id, [calculation, calculation, batch]
        )
        runtimes.append(runtime)
        return runtime

    agent.runtime_factory = factory
    result = await agent.run(AgentRequest(query="q", collection="swin_v1"))
    assert runtimes[0].seen_tool_names[-1] == ["submit_claims"]
    assert result.answer is None and result.usage.answer_calls == 0


@pytest.mark.asyncio
async def test_final_draft_has_fresh_messages_and_exact_retained_evidence(tmp_path):
    calculation = action("calculate", {"expression": "1+1", "evidence_ids": ["lr"]})
    agent = verified_agent(tmp_path, [SEARCH, calculation, SUBMIT])
    snapshots = []

    class CapturingRuntime(WorkflowRuntime):
        async def plan(self, messages, tools):
            snapshots.append(json.loads(json.dumps(messages)))
            return await super().plan(messages, tools)

    agent.runtime_factory = lambda root, config, journal, task_id: CapturingRuntime(
        root, config, journal, task_id, [SEARCH, calculation, SUBMIT]
    )
    request = AgentRequest(
        query="author motivation",
        collection="swin_v1",
        required_claim_kinds=["inference"],
    )
    result = await agent.run(request)
    assert result.status == "review_required" and result.usage.answer_calls == 1
    assert [message["role"] for message in snapshots[-1]] == ["system", "user"]
    payload = json.loads(snapshots[-1][1]["content"])
    assert payload["request"] == request.model_dump(mode="json")
    assert payload["evidence"][0]["text"] == fixtures.ROWS[0]["chunk"]["text"]
    assert payload["tool_artifacts"][0]["result"] == "2"
    assert "tool_calls" not in snapshots[-1][1]["content"]


@pytest.mark.asyncio
async def test_dropped_verified_evidence_stops_before_paid_generation(
    tmp_path, monkeypatch
):
    from ican.agent import environment

    original = environment.prepare_evidence

    async def drop_context(*args, **kwargs):
        prepared = await original(*args, **kwargs)
        prepared.registry.clear()
        return prepared

    monkeypatch.setattr(environment, "prepare_evidence", drop_context)
    agent = verified_agent(tmp_path, [SEARCH, SUBMIT])
    result = await agent.run(AgentRequest(query="q", collection="swin_v1"))
    assert result.status == "failed" and result.answer is None
    assert result.usage.answer_calls == 0
    assert result.artifacts[0]["kind"] == "claim_verification"


@pytest.mark.asyncio
async def test_source_assert_is_verified_before_cited_blocked_answer(
    tmp_path, monkeypatch
):
    source = "assert H % 2 == 0 and W % 2 == 0\n"
    target = tmp_path / "repo/main.py"
    target.parent.mkdir()
    target.write_text(source, encoding="utf-8", newline="\n")
    row = fixtures.row()
    row.update(
        text=source, source_sha256=hashlib.sha256(target.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(fixtures, "ROWS", [{"collection": "swin_v1", "chunk": row}])

    class BlockedRuntime(FakeRuntime):
        async def request(self, role, messages, tools=None):
            self.record(role)
            context = messages[1]["content"]
            assert '"status": "blocked_by_precondition"' in context
            cid = re.search(r"pqac-[0-9a-f]{8}", context)[0]
            return {"role": "assistant", "content": f"7×7不满足偶数前置断言 ({cid})。"}

    draft = {
        "statement": "The merge can run for a 7 by 7 grid.",
        "kind": "code_execution",
        "evidence_ids": ["lr"],
        "conditions": [{"chunk_id": "lr", "bindings": {"H": 7, "W": 7}}],
    }
    submit = action("submit_claims", {"evidence_ids": ["lr"], "claims": [draft]})
    agent = verified_agent(tmp_path, [SEARCH, submit], runtime_class=BlockedRuntime)
    request = AgentRequest(
        query="can merge run",
        collection="swin_v1",
        required_claim_kinds=["code_execution"],
    )
    result = await agent.run(request)
    assert result.status == "completed"
    verdict = result.artifacts[0]["verdicts"][0]
    assert verdict["status"] == "blocked_by_precondition"
    assert verdict["conditions"][0]["line"] == 1
    assert result.usage.answer_calls == 1
