import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ican.agent.schema import AgentConfig, AgentRequest, ToolInputError
from ican.api.app import create_app
from ican.research.auto_schema import (
    AutoCardRequest,
    ComparisonRequest,
    DiscoveryRequest,
)
from ican.research.auto_service import ResearchAutoService
from ican.research.schema import ClaimDraft, ScreeningDraft
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.schema import (
    EvidenceResult,
    EvidenceSource,
    SearchResponse,
)


def evidence(cid, source, text, rank):
    return EvidenceResult(
        rank=rank,
        score=1 / rank,
        chunk_id=cid,
        text=text,
        review_required=False,
        source=EvidenceSource(
            source_id=source,
            source_type="paper",
            source_path=f"papers/{source}.pdf",
            source_version="v1",
            location={"page": rank},
        ),
    )


ITEMS = [
    evidence("a1", "paper-a", "Model A uses ImageNet and top-1 accuracy.", 1),
    evidence("a2", "paper-a", "Model A training lasts 100 epochs.", 2),
    evidence("b1", "paper-b", "Model B uses CIFAR and classification accuracy.", 3),
]


class Search:
    def search(self, request):
        selected = [item for item in ITEMS if item.source.source_type == "paper"]
        if request.filters.path_prefixes:
            selected = [
                item
                for item in selected
                if any(
                    item.source.source_path.startswith(prefix)
                    for prefix in request.filters.path_prefixes
                )
            ]
        return SearchResponse(
            index_fingerprint="a" * 64,
            collection=request.collection,
            query=request.query,
            filters=request.filters,
            results=selected,
        )


class Corpus:
    def __init__(self, request):
        self.request = request

    def evidence(self, cid):
        item = next((item for item in ITEMS if item.chunk_id == cid), None)
        if item is None or (
            self.request.filters.path_prefixes
            and item.source.source_path not in self.request.filters.path_prefixes
        ):
            raise ToolInputError("Evidence is outside the selected paper")
        return item


class Runtime:
    def __init__(self, draft):
        self.draft = draft
        self.records = []

    async def request(self, role, messages, tools):
        assert role == "answer" and len(tools) == 1
        assert tools[0]["function"]["name"] == "submit_research_card"
        payload = json.loads(messages[1]["content"])
        assert len(payload["evidence"]) <= 6
        self.records.append({"usage": {"prompt_tokens": 25, "completion_tokens": 30}})
        return {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "submit_research_card",
                        "arguments": json.dumps(self.draft),
                    }
                }
            ],
        }


class MalformedRuntime:
    def __init__(self):
        self.records = [{"usage": {"prompt_tokens": 1, "completion_tokens": 1}}]

    async def request(self, role, messages, tools):
        return {"role": "assistant", "tool_calls": [{}]}


def field(name, value, quote, cid):
    return {"name": name, "value": value, "quote": quote, "evidence_id": cid}


def draft_a():
    return {
        "decision": "include",
        "reason": "Relevant image model.",
        "reason_evidence_ids": ["a1"],
        "fields": [
            field("model", "Model A", "Model A uses", "a1"),
            field("dataset", "ImageNet", "ImageNet", "a1"),
            field("metric", "top-1 accuracy", "top-1 accuracy", "a1"),
            field("training", "100 epochs", "100 epochs", "a2"),
        ],
    }


def draft_b():
    return {
        "decision": "hold",
        "reason": "Needs comparison review.",
        "reason_evidence_ids": ["b1"],
        "fields": [
            field("model", "Model B", "Model B uses", "b1"),
            field("dataset", "CIFAR", "CIFAR", "b1"),
            field("metric", "classification accuracy", "classification accuracy", "b1"),
        ],
    }


def build(tmp_path, drafts):
    config = tmp_path / "configs/agent/v2.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        AgentConfig(
            version="p4-agent-v2", workflow_mode="verified", max_planner_calls=3
        ).model_dump_json(),
        encoding="utf-8",
    )
    rows = [
        {
            "collection": "swin_v1",
            "chunk": {
                "source_id": item.source.source_id,
                "source_type": "paper",
                "source_path": item.source.source_path,
                "source_version": item.source.source_version,
                "location": item.source.location,
                "text": item.text,
            },
        }
        for item in ITEMS
    ]
    search = Search()
    research = ResearchService(
        tmp_path,
        None,
        search,
        corpus_factory=lambda root, config, evidence_service, request: Corpus(request),
        store=ResearchStore(tmp_path / "records"),
    )
    pending = iter(drafts)
    auto = ResearchAutoService(
        tmp_path,
        None,
        search,
        research,
        rows=rows,
        titles={"paper-a": "Paper A", "paper-b": "Paper B"},
        runtime_factory=lambda root, config, journal, task_id: Runtime(next(pending)),
        corpus_factory=lambda root, config, evidence_service, request, rows: Corpus(
            request
        ),
    )
    return auto


def test_discovery_groups_chunks_by_paper_and_keeps_titles(tmp_path):
    auto = build(tmp_path, [])
    result = auto.discover(DiscoveryRequest(query="image models", collection="swin_v1"))
    assert [item.title for item in result.candidates] == ["Paper A", "Paper B"]
    assert [item.chunk_id for item in result.candidates[0].evidence] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_auto_card_is_scoped_and_preserves_revisions_and_verdicts(tmp_path):
    altered = draft_a()
    altered["fields"].append(field("limitation", "a normalized claim", "Model A", "a1"))
    altered["fields"].append(field("result", "ImageNet", "ImageNet absent", "a1"))
    auto = build(tmp_path, [altered])
    result = await auto.auto_card(
        AutoCardRequest(query="image models", collection="swin_v1", source_id="paper-a")
    )
    assert result.screening.claims[0].status == "requires_review"
    assert result.extraction is not None
    statuses = {
        field.name: field.claims[0].status for field in result.extraction.fields
    }
    assert statuses["model"] == "supported"
    assert statuses["limitation"] == "requires_review"
    assert statuses["result"] == "insufficient_evidence"
    assert result.screening.card_id == result.extraction.card_id
    assert result.screening.card_id is not None
    assert result.usage.paid_calls == 1
    assert len(list((tmp_path / "records").glob("*.json"))) == 2


@pytest.mark.asyncio
async def test_auto_card_rejects_cross_paper_evidence_without_writing(tmp_path):
    bad = draft_a()
    bad["reason_evidence_ids"] = ["b1"]
    auto = build(tmp_path, [bad])
    with pytest.raises(ToolInputError, match="outside the selected paper"):
        await auto.auto_card(
            AutoCardRequest(
                query="image models", collection="swin_v1", source_id="paper-a"
            )
        )
    assert list((tmp_path / "records").glob("*.json")) == []


@pytest.mark.asyncio
async def test_empty_card_is_rejected_without_replacing_prior_complete_card(tmp_path):
    empty = draft_a()
    empty["fields"] = []
    auto = build(tmp_path, [draft_a(), empty])
    request = AutoCardRequest(
        query="image models", collection="swin_v1", source_id="paper-a"
    )
    first = await auto.auto_card(request)
    with pytest.raises(ToolInputError, match="invalid"):
        await auto.auto_card(request)
    saved = auto.load_card(request)
    assert saved.screening.record_id == first.screening.record_id
    assert saved.extraction.record_id == first.extraction.record_id


@pytest.mark.asyncio
async def test_malformed_model_tool_call_is_a_bounded_input_error(tmp_path):
    auto = build(tmp_path, [])
    auto.runtime_factory = lambda root, config, journal, task_id: MalformedRuntime()
    with pytest.raises(ToolInputError, match="malformed_tool_call"):
        await auto.auto_card(
            AutoCardRequest(
                query="image models", collection="swin_v1", source_id="paper-a"
            )
        )
    traces = list((tmp_path / "data/processed/research/p4-v2/tasks").glob("*.json"))
    assert len(traces) == 1
    trace = json.loads(traces[0].read_text(encoding="utf-8"))
    assert trace["submission_diagnostic"]["code"] == "malformed_tool_call"


@pytest.mark.asyncio
async def test_compare_reports_incompatible_conditions_and_cited_positions(tmp_path):
    auto = build(tmp_path, [draft_a(), draft_b()])
    cards = [
        await auto.auto_card(
            AutoCardRequest(
                query="image models", collection="swin_v1", source_id=source
            )
        )
        for source in ("paper-a", "paper-b")
    ]
    result = auto.compare(
        ComparisonRequest(record_ids=[card.extraction.record_id for card in cards])
    )
    assert result.comparable is False
    assert any("dataset" in warning for warning in result.warnings)
    assert "papers/paper-a.pdf:p.1" in result.markdown
    assert "papers/paper-b.pdf:p.3" in result.markdown
    assert "不可直接横向排名" in result.markdown
    assert "100 epochs" in result.markdown


def test_new_endpoints_forward_and_reject_invalid_collection(tmp_path):
    auto = build(tmp_path, [])
    client = TestClient(create_app(root=Path(tmp_path), research_auto_service=auto))
    assert (
        client.post(
            "/v1/research/discover",
            json={"query": "image models", "collection": "swin_v1"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/research/discover",
            json={"query": "image models", "collection": "qasper_validation_v1"},
        ).status_code
        == 422
    )


@pytest.mark.asyncio
async def test_saved_card_loads_latest_human_revision_without_model_call(tmp_path):
    auto = build(tmp_path, [draft_a()])
    request = AutoCardRequest(
        query="image models", collection="swin_v1", source_id="paper-a"
    )
    generated = await auto.auto_card(request)
    revised = auto.research.submit_screening(
        AgentRequest(
            query="image models",
            collection="swin_v1",
            family="swin_v1",
            filters={
                "source_types": ["paper"],
                "path_prefixes": ["papers/paper-a.pdf"],
            },
        ),
        ScreeningDraft(
            subject_source_id="paper-a",
            decision="hold",
            revision_of=generated.screening.record_id,
            claims=[
                ClaimDraft(
                    statement="A researcher requests review.",
                    kind="inference",
                    evidence_ids=["a1"],
                )
            ],
        ),
    )
    client = TestClient(create_app(root=Path(tmp_path), research_auto_service=auto))
    response = client.post("/v1/research/load-card", json=request.model_dump())
    assert response.status_code == 200
    saved = response.json()
    assert saved["screening"]["record_id"] == str(revised.record_id)
    assert saved["screening"]["revision_of"] == str(generated.screening.record_id)
    assert saved["screening"]["card_id"] == str(generated.screening.card_id)
    assert saved["extraction"]["record_id"] == str(generated.extraction.record_id)
    assert saved["usage"]["paid_calls"] == 0


@pytest.mark.asyncio
async def test_saved_card_rejects_changed_source_version(tmp_path):
    auto = build(tmp_path, [draft_a()])
    request = AutoCardRequest(
        query="image models", collection="swin_v1", source_id="paper-a"
    )
    await auto.auto_card(request)
    for item in auto._rows:
        if item["chunk"]["source_id"] == "paper-a":
            item["chunk"]["source_version"] = "v2"
    with pytest.raises(ToolInputError, match="No evidence"):
        auto.load_card(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [1, 8])
async def test_multi_entries_survive_persistence_revision_and_comparison(
    tmp_path, extra
):
    from ican.research.schema import ExtractionDraft, ExtractionFieldDraft

    draft = draft_a()
    draft["fields"].extend(
        field("dataset", f"second dataset {i}", f"second dataset {i}", "a2")
        for i in range(extra)
    )
    auto = build(tmp_path, [draft, draft_b()])
    request = AutoCardRequest(
        query="image models", collection="swin_v1", source_id="paper-a"
    )
    first = await auto.auto_card(request)
    second = await auto.auto_card(
        AutoCardRequest(query="image models", collection="swin_v1", source_id="paper-b")
    )
    loaded = auto.load_card(request)
    assert [f.value for f in loaded.extraction.fields] == [
        f["value"] for f in draft["fields"]
    ]
    assert loaded.extraction.fields[-1].claims[0].status == "insufficient_evidence"
    revised = auto.research.submit_extraction(
        auto._paper_scope(request, first.candidate),
        ExtractionDraft(
            subject_source_id="paper-a",
            revision_of=first.extraction.record_id,
            fields=[
                ExtractionFieldDraft(
                    name=f.name, value=f.value, claims=[v.claim for v in f.claims]
                )
                for f in loaded.extraction.fields
            ],
        ),
    )
    assert auto.load_card(request).extraction == revised
    report = auto.compare(
        ComparisonRequest(record_ids=[revised.record_id, second.extraction.record_id])
    )
    assert not report.comparable
    assert any("尚未绑定实验关联" in w for w in report.warnings)
    table = report.markdown.split("## 可比性")[0]
    assert "ImageNet" in table and "second dataset" in table
    assert "insufficient_evidence" in table
