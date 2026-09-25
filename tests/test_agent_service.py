import asyncio
import json
import re
from pathlib import Path

import pytest

from ican.agent.corpus import AgentCorpus
from ican.agent.journal import PaidJournal
from ican.agent.schema import AgentConfig, AgentRequest, BudgetExhausted, ToolInputError
from ican.agent.service import AgentService
from ican.qa.runtime import ModelTimeout
from ican.retrieval.schema import EvidenceResult, EvidenceSource, SearchResponse


def row(cid="lr", path="repo/main.py", structure="main"):
    return {
        "chunk_id": cid,
        "source_type": "code",
        "source_path": path,
        "source_id": "source",
        "source_version": "commit",
        "location": {"line_start": 1, "line_end": 3},
        "text": "base_lr = 5e-4 * batch * world_size / 512 * accumulation\n",
        "review_required": False,
        "char_start": 0,
        "structure_name": structure,
    }


ROWS = [
    {"collection": "swin_v1", "chunk": row()},
    {
        "collection": "swin_v1",
        "chunk": row(
            "wrong", "repo/models/swin_transformer_v2.py", "PatchMerging.forward"
        ),
    },
]


class EvidenceService:
    def __init__(self):
        self.requests = []
        self.fingerprint = "a" * 64

    def _load_index(self):
        return Path("indexes") / ("a" * 64), {"collections": {"swin_v1": {}}}

    def search(self, request):
        self.requests.append(request)
        r = ROWS[0]["chunk"]
        e = EvidenceResult(
            rank=1,
            score=0.8,
            chunk_id=r["chunk_id"],
            text=r["text"],
            review_required=False,
            source=EvidenceSource(
                **{
                    k: r[k]
                    for k in [
                        "source_type",
                        "source_path",
                        "source_id",
                        "source_version",
                        "location",
                    ]
                }
            ),
        )
        return SearchResponse(
            index_fingerprint=self.fingerprint,
            collection=request.collection,
            query=request.query,
            filters=request.filters,
            results=[e],
        )


def action(name, args, call_id="call1"):
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


SEARCH = action(
    "search_evidence",
    {"query": "Swin-T base LR main", "source_types": ["code"], "strategy": "bm25"},
)
CALC = action("calculate", {"expression": "5e-4*128*8/512*2", "evidence_ids": ["lr"]})
ANSWER = action("gen_answer", {"evidence_ids": ["lr"]})
VERIFY_INFERENCE = action(
    "verify_claims",
    {
        "claims": [
            {
                "statement": "This implementation is likely faster.",
                "kind": "inference",
                "evidence_ids": ["lr"],
            }
        ]
    },
)


class FakeRuntime:
    def __init__(self, root, config, journal, task_id, actions, delay=0):
        self.config, self.actions, self.delay = config, list(actions), delay
        self.records = []
        self.seen_tool_names = []
        self.journal, self.task_id = journal, task_id

    def record(self, role):
        call_id = self.journal.reserve(self.task_id, role, "fake")
        usage = {"prompt_tokens": 20, "completion_tokens": 10}
        self.records.append({"role": role, "usage": usage, "response_model": "fake"})
        self.journal.finish(
            call_id, status="completed", response_model="fake", usage=usage
        )

    async def plan(self, messages, tools):
        self.seen_tool_names.append([t["function"]["name"] for t in tools])
        self.record("planner")
        await asyncio.sleep(self.delay)
        return self.actions.pop(0)

    async def request(self, role, messages, tools=None):
        self.record(role)
        cid = re.search(r"pqac-[0-9a-f]{8}", messages[1]["content"])[0]
        assert '"result": "0.002"' in messages[1]["content"]
        return {"role": "assistant", "content": f"缩放后学习率为0.002 ({cid})。"}


def service(tmp_path, actions, config=None, max_paid=40, delay=0):
    evidence = EvidenceService()
    journal = PaidJournal(tmp_path / "paid.jsonl", max_paid)
    factory = lambda root, cfg, svc, req: AgentCorpus(root, cfg, svc, req, rows=ROWS)
    runtime = lambda root, cfg, j, tid: FakeRuntime(root, cfg, j, tid, actions, delay)
    return AgentService(
        tmp_path, None, evidence, config or AgentConfig(), factory, runtime, journal
    ), evidence


REQUEST = AgentRequest(
    query="Swin-T的学习率，batch128、8卡、accumulation2", collection="swin_v1"
)


@pytest.mark.asyncio
async def test_reserved_finalization_uses_native_model_choice_within_budget(tmp_path):
    agent, _ = service(
        tmp_path, [SEARCH, CALC, ANSWER], AgentConfig(max_planner_calls=3)
    )
    original_factory, runtimes = agent.runtime_factory, []

    def capture(*args):
        runtime = original_factory(*args)
        runtimes.append(runtime)
        return runtime

    agent.runtime_factory = capture
    result = await agent.run(REQUEST)
    assert result.status == "completed" and result.usage.paid_calls == 4
    assert runtimes[0].seen_tool_names[-1] == ["gen_answer"]
    assert result.usage.planner_calls == 3 and result.usage.answer_calls == 1


@pytest.mark.asyncio
async def test_finalization_rejects_extra_investigation_without_automatic_answer(
    tmp_path,
):
    agent, _ = service(tmp_path, [SEARCH, CALC], AgentConfig(max_planner_calls=2))
    result = await agent.run(REQUEST)
    assert result.status == "budget_exhausted"
    assert result.artifacts == [] and result.answer is None
    assert result.usage.paid_calls == 2 and result.usage.answer_calls == 0


@pytest.mark.asyncio
async def test_actual_paperqa_environment_multi_step_calculation_answer_and_history(
    tmp_path,
):
    agent, evidence = service(tmp_path, [SEARCH, CALC, ANSWER])
    result = await agent.run(REQUEST)
    assert result.status == "completed" and "0.002" in result.answer.answer
    assert result.answer.prompt_version == "p4-tools-evidence-v1"
    assert result.artifacts[0]["result"] == "0.002"
    assert result.usage.paid_calls == 4 and result.usage.answer_calls == 1
    assert evidence.requests[0].family == "swin_v1"
    record = json.loads(
        (
            tmp_path / f"data/processed/agent/p4-v1/tasks/{result.task_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert record["paperqa_tool_history"] == [
        ["search_evidence"],
        ["calculate"],
        ["gen_answer"],
    ]
    assert (
        record["raw_answer"]
        and result.answer.citations[0].evidence.text == ROWS[0]["chunk"]["text"]
    )


@pytest.mark.asyncio
async def test_native_research_claim_tool_uses_only_retained_evidence(tmp_path):
    agent, _ = service(
        tmp_path,
        [SEARCH, VERIFY_INFERENCE, action("complete", {"has_successful_answer": True})],
        AgentConfig(max_planner_calls=3),
    )
    result = await agent.run(REQUEST)
    assert result.status == "budget_exhausted"
    assert result.artifacts[0]["kind"] == "claim_verification"
    assert result.artifacts[0]["verdicts"][0]["status"] == "requires_review"
    assert result.trajectory[3]["name"] == "verify_claims"
    assert result.trajectory[3]["turn"] == 2
    assert result.trajectory[3]["arguments"]["claims"][0]["kind"] == "inference"


@pytest.mark.asyncio
async def test_native_research_claim_tool_rejects_unretained_evidence(tmp_path):
    bad = action(
        "verify_claims",
        {
            "claims": [
                {
                    "statement": "An unsupported inference.",
                    "kind": "inference",
                    "evidence_ids": ["wrong"],
                }
            ]
        },
    )
    agent, _ = service(tmp_path, [SEARCH, bad], AgentConfig(max_planner_calls=2))
    result = await agent.run(REQUEST)
    assert result.artifacts == []
    assert result.trajectory[-1]["result"] == json.dumps(
        {"error": "Invalid tool name, JSON or arguments"}
    )


@pytest.mark.asyncio
async def test_no_fake_completion_no_automatic_generation_at_step_limit(tmp_path):
    agent, _ = service(
        tmp_path,
        [action("complete", {"has_successful_answer": True})],
        AgentConfig(max_planner_calls=1),
    )
    result = await agent.run(REQUEST)
    assert result.status == "budget_exhausted" and result.answer is None
    assert result.usage.answer_calls == 0


@pytest.mark.asyncio
async def test_repeated_actions_cache_and_stop_without_extra_retrieval(tmp_path):
    agent, evidence = service(tmp_path, [SEARCH, SEARCH, SEARCH])
    result = await agent.run(REQUEST)
    assert result.status == "no_progress"
    assert len(evidence.requests) == 1 and result.usage.answer_calls == 0
    assert sum(t.get("cached", False) for t in result.trajectory) == 2


@pytest.mark.asyncio
async def test_unknown_tool_and_reserved_state_cannot_be_dispatched(tmp_path):
    invalid = action(
        "calculate", {"expression": "1+1", "evidence_ids": [], "state": {}}
    )
    agent, _ = service(tmp_path, [action("shell", {"cmd": "anything"}), invalid])
    result = await agent.run(REQUEST)
    assert result.status == "no_progress" and result.artifacts == []


@pytest.mark.asyncio
async def test_fingerprint_change_stops_before_answer(tmp_path):
    agent, evidence = service(tmp_path, [SEARCH])
    evidence.fingerprint = "b" * 64
    result = await agent.run(REQUEST)
    assert result.status == "failed" and result.answer is None
    assert result.usage.answer_calls == 0


@pytest.mark.asyncio
async def test_paid_budget_reserved_before_answer_and_timeout_no_retry(tmp_path):
    agent, _ = service(tmp_path, [SEARCH, CALC, ANSWER], max_paid=2)
    result = await agent.run(REQUEST)
    assert result.status == "budget_exhausted" and result.usage.paid_calls == 2
    other, _ = service(
        tmp_path / "timeout", [SEARCH], AgentConfig(task_timeout_seconds=0.01), delay=1
    )
    result = await other.run(REQUEST)
    assert result.status == "timed_out" and result.usage.answer_calls == 0


def test_corpus_fixed_family_scope_unknown_ids_and_type_intersection(tmp_path):
    service = EvidenceService()
    corpus = AgentCorpus(tmp_path, None, service, REQUEST, rows=ROWS)
    with pytest.raises(ToolInputError):
        corpus.evidence("wrong")
    with pytest.raises(ToolInputError):
        corpus.evidence("absent")
    req = AgentRequest(
        query="Swin-T",
        collection="swin_v1",
        filters={"source_types": ["code"], "path_prefixes": ["repo/main.py"]},
    )
    corpus = AgentCorpus(tmp_path, None, service, req, rows=ROWS)
    assert corpus.search_request("new", ["paper"], "dense") is None
    assert corpus.search_request("Swin V2", [], "dense").family == "swin_v1"
    with pytest.raises(ToolInputError):
        corpus.source_text(".env")


def test_journal_started_only_calls_consumed_and_new_instance_cannot_reset_cap(
    tmp_path,
):
    path = tmp_path / "journal.jsonl"
    first = PaidJournal(path, 1)
    first.reserve("task", "planner", "model")
    with pytest.raises(BudgetExhausted):
        PaidJournal(path, 1).reserve("newtask", "planner", "model")


@pytest.mark.parametrize(
    "calls",
    [
        [{"id": "x", "type": "function"}],
        [{"type": "function", "function": {"name": "calculate", "arguments": "{}"}}],
        ["bad"],
        "bad",
        [None],
    ],
)
@pytest.mark.asyncio
async def test_malformed_tool_structure_is_a_bounded_failure(tmp_path, calls):
    agent, _ = service(tmp_path, [{"role": "assistant", "tool_calls": calls}])
    result = await agent.run(REQUEST)
    assert result.status == "failed" and result.answer is None
    assert result.usage.paid_calls == 1 and result.usage.answer_calls == 0


@pytest.mark.asyncio
async def test_actual_paperqa_answer_timeout_is_preserved_and_never_retried(tmp_path):
    class TimeoutRuntime(FakeRuntime):
        async def request(self, role, messages, tools=None):
            self.record(role)
            raise ModelTimeout("Timeout")

    agent, _ = service(tmp_path, [SEARCH, ANSWER])
    agent.runtime_factory = lambda root, cfg, j, tid: TimeoutRuntime(
        root, cfg, j, tid, [SEARCH, ANSWER]
    )
    result = await agent.run(REQUEST)
    assert result.status == "timed_out" and result.answer is None
    assert result.usage.answer_calls == 1


@pytest.mark.asyncio
async def test_planner_cannot_label_invented_overrides_as_user_input(tmp_path):
    call = action(
        "trace_config",
        {
            "config_path": "target.yaml",
            "field": "MODEL.DROP_PATH_RATE",
            "opts": ["MODEL.DROP_PATH_RATE", "0.9"],
            "cli": {},
        },
    )
    agent, _ = service(tmp_path, [call], AgentConfig(max_planner_calls=1))
    result = await agent.run(REQUEST)
    assert result.artifacts == [] and result.answer is None
    assert "structured user_overrides" in result.trajectory[-1]["result"]
