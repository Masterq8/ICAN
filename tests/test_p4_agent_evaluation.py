from __future__ import annotations

from pathlib import Path

import pytest

from ican.agent.schema import AgentResponse, AgentUsage
from ican.evaluation.data import Case


def _case(dataset: str, split: str, case_id: str) -> Case:
    return Case(
        id=case_id,
        dataset=dataset,
        split=split,
        question=f"question {case_id}",
        collection="swin_v1" if dataset == "swin" else "qasper_validation_v1",
        filters={} if dataset == "swin" else {"path_prefixes": [f"qasper/{case_id}"]},
    )


def test_cases_are_fixed_without_parsing_frozen_test(tmp_path, monkeypatch):
    from ican.evaluation import p4_agent

    inputs = [
        *[_case("swin", "dev", f"swin_dev_{number:02d}") for number in range(1, 13)],
        *[_case("qasper", "validation", f"question-{number}") for number in range(8)],
    ]
    monkeypatch.setattr(
        p4_agent,
        "load_inputs",
        lambda root: (inputs, {"not_used_for_selection": True}, {"fixed": "abc"}),
    )
    monkeypatch.setattr(p4_agent, "digest", lambda path: "frozen-digest")
    monkeypatch.setattr(p4_agent, "FROZEN_SHA256", "frozen-digest")

    cases, identity = p4_agent.build_p44_cases(Path(tmp_path))

    assert [case.key for case in cases[:4]] == [
        "swin/dev/swin_dev_06",
        "swin/dev/swin_dev_05",
        "swin/dev/swin_dev_04",
        "swin/dev/swin_dev_12",
    ]
    assert len(cases) == 8
    assert identity["frozen_test_sha256"] == "frozen-digest"


def test_manifest_rejects_an_identity_change(tmp_path):
    from ican.evaluation.p4_agent import write_manifest

    write_manifest(tmp_path, {"version": "p4-v2", "fixed": "first"})

    try:
        write_manifest(tmp_path, {"version": "p4-v2", "fixed": "second"})
    except ValueError as error:
        assert "identity changed" in str(error)
    else:
        raise AssertionError("the immutable manifest was overwritten")


def test_planner_requires_typed_claims_for_execution_and_inference():
    from ican.agent.prompts import PLANNER_SYSTEM

    assert "code_execution" in PLANNER_SYSTEM
    assert "inference" in PLANNER_SYSTEM


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run(self, request):
        self.calls.append(request)
        return AgentResponse(
            task_id="task-1",
            status="completed",
            stop_reason="final_answer_generated",
            planner_model="fake-planner",
            answer_model="fake-answer",
            usage=AgentUsage(paid_calls=1, planner_calls=1),
        )


@pytest.mark.asyncio
async def test_started_case_is_never_retried(tmp_path):
    from ican.agent.schema import AgentRequest
    from ican.evaluation.p4_agent import P4AgentCase, P4AgentEvaluationRunner

    case = P4AgentCase(
        key="swin/dev/swin_dev_06",
        request=AgentRequest(query="learning rate", collection="swin_v1"),
    )
    agent = FakeAgent()
    runner = P4AgentEvaluationRunner(tmp_path, [case], {"version": "test"}, agent)

    await runner.run_case(case)

    with pytest.raises(ValueError, match="already recorded"):
        await runner.run_case(case)
    assert len(agent.calls) == 1


@pytest.mark.asyncio
async def test_audit_requires_shape_and_motivation_claim_states(tmp_path):
    from ican.agent.schema import AgentRequest
    from ican.evaluation.p4_agent import (
        P4AgentCase,
        P4AgentEvaluationRunner,
        audit_run,
    )

    cases = [
        P4AgentCase(
            key="swin/dev/swin_dev_04",
            request=AgentRequest(query="shape", collection="swin_v1"),
            required_claim_status="blocked_by_precondition",
        ),
        P4AgentCase(
            key="swin/dev/swin_dev_12",
            request=AgentRequest(query="motivation", collection="swin_v1"),
            required_claim_status="requires_review",
        ),
    ]
    runner = P4AgentEvaluationRunner(tmp_path, cases, {"version": "test"}, FakeAgent())
    for case in cases:
        await runner.run_case(case)

    report = audit_run(tmp_path, cases, {"version": "test"})

    assert report["status"] == "failed"
    assert "swin/dev/swin_dev_04:claim_status_missing" in report["failures"]
    assert "swin/dev/swin_dev_12:claim_status_missing" in report["failures"]
