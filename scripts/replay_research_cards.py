"""Replay sealed model actions through v2 services without network or paid models."""

from __future__ import annotations

import asyncio
import hashlib
import json
import socket
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.research_audit import verify_audit_inputs
from ican.research.auto_schema import AutoCardRequest, ComparisonRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.research.submission import diagnose_card_submission
from ican.retrieval.schema import EvidenceResult, SearchResponse


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NoPaidJournal:
    def reserve(self, *args, **kwargs):
        raise AssertionError("Paid calls are forbidden during replay")


class FrozenCorpus:
    def __init__(self, items):
        self.items = {item.chunk_id: item for item in items}

    def evidence(self, chunk_id):
        return self.items[chunk_id]


class FrozenSearch:
    def __init__(self, items):
        self.items = items

    def search(self, request):
        return SearchResponse(
            index_fingerprint="0" * 64,
            query=request.query,
            collection=request.collection,
            filters=request.filters,
            results=self.items,
        )


class ReplayRuntime:
    def __init__(self, action, items):
        self.action, self.items = action, items
        self.records = []

    async def request(self, role, messages, tools):
        expected = [{"chunk_id": x.chunk_id, "text": x.text[:2200]} for x in self.items]
        assert json.loads(messages[1]["content"])["evidence"] == expected
        self.records.append({"paid": False, "usage": {}, "mode": "offline_replay"})
        return self.action


async def replay():
    frozen = ROOT / "data/processed/evaluation/p46-quality-v1"
    original_docs = ROOT / "docs/evaluation/p46-quality-v1"
    manifest = read(frozen / "manifest.json")
    verify_audit_inputs(ROOT, frozen, manifest, read(original_docs / "run-seal.json"))
    output = ROOT / "data/processed/evaluation/p46-multi-entry-replay-v1" / uuid4().hex
    store = ResearchStore(output / "records")
    results, cards = {}, []
    for key, case in manifest["cases"].items():
        old = read(frozen / f"{key}.result.json")
        trace = read(frozen / "traces" / old["trace"])
        action = trace["model_action"]
        items = [EvidenceResult.model_validate(e) for e in case["evidence"]]
        allowed = {item.chunk_id for item in items}
        legacy = diagnose_card_submission(action, allowed, legacy=True)
        current = diagnose_card_submission(action, allowed)
        assert legacy.code == old["tool_diagnosis"]["code"]
        assert current.draft is not None
        corpus, search = FrozenCorpus(items), FrozenSearch(items)
        research = ResearchService(
            ROOT,
            None,
            search,
            store=store,
            corpus_factory=lambda *args, c=corpus, **kwargs: c,
        )
        rows = [
            {
                "collection": case["request"]["collection"],
                "chunk": {
                    **item.source.model_dump(),
                    "text": item.text,
                },
            }
            for item in items
        ]
        auto = ResearchAutoService(
            ROOT,
            None,
            search,
            research,
            rows=rows,
            titles={case["request"]["source_id"]: case["title"]},
            corpus_factory=lambda *args, c=corpus, **kwargs: c,
            runtime_factory=lambda *args, a=action, e=items: ReplayRuntime(a, e),
            journal=NoPaidJournal(),
            trace_directory=output / "traces",
        )
        request = AutoCardRequest.model_validate(case["request"])
        card = await auto.auto_card(request)
        loaded = auto.load_card(request)
        assert card.usage.paid_calls == loaded.usage.paid_calls == 0
        assert loaded.extraction == card.extraction
        assert loaded.extraction is not None
        fields = loaded.extraction.fields
        assert [(f.name, f.value) for f in fields] == [
            (f.name, f.value) for f in current.draft.fields
        ]
        for actual, raw in zip(fields, current.draft.fields, strict=True):
            assert actual.claims[0].claim.evidence_ids == [raw.evidence_id]
        cards.append(card)
        results[key] = {
            "original_diagnostic": legacy.code,
            "replay_diagnostic": current.code,
            "preserved_entries": len(fields),
            "names": dict(Counter(f.name for f in fields)),
            "claim_statuses": dict(Counter(f.claims[0].status for f in fields)),
            "original_trace_sha256": digest(frozen / "traces" / old["trace"]),
            "record_id": str(loaded.extraction.record_id),
        }
    comparisons = []
    for first, second in zip(cards[::2], cards[1::2], strict=True):
        report = auto.compare(
            ComparisonRequest(
                record_ids=[first.extraction.record_id, second.extraction.record_id]
            )
        )
        assert not report.comparable
        assert any("尚未绑定实验关联" in warning for warning in report.warnings)
        for card in (first, second):
            for field in card.extraction.fields:
                assert auto._cell(field.value) in report.markdown
        comparisons.append(report.model_dump(mode="json"))
    changed = [
        ROOT / p
        for p in (
            "ican/research/auto_schema.py",
            "ican/research/schema.py",
            "ican/research/auto_service.py",
            "ican/research/submission.py",
            "ican/research/service.py",
            "frontend/src/App.vue",
            "frontend/src/api.ts",
            "scripts/replay_research_cards.py",
        )
    ]
    summary = {
        "kind": "offline_replay_not_new_model_evaluation",
        "paid_calls": 0,
        "frozen_manifest_sha256": digest(frozen / "manifest.json"),
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in changed},
        "cases": results,
        "comparisons": comparisons,
        "runtime_directory": output.relative_to(ROOT).as_posix(),
    }
    docs = ROOT / "docs/evaluation/p46-multi-entry-replay-v1"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = [
        "# 同类字段多条目：离线回放",
        "",
        "6份原失败输出与2份原成功输出均通过新协议提交、持久化、加载及报告检查，59个条目按原顺序保留。",
        "这是已保存动作的离线兼容性测试，不是新模型成功率；原始真实评测仍为2/8。付费调用0，网络连接被禁止。",
        "多条目尚未建立实验关联，因此比较不自动排名；不修复原有引用或类型错误。",
        "",
        "| 样本 | 原诊断 | 新协议诊断 | 保留条目 |",
        "|---|---|---|---|",
    ]
    rows += [
        f"| {k} | {v['original_diagnostic']} | {v['replay_diagnostic']} | {v['preserved_entries']} |"
        for k, v in results.items()
    ]
    (docs / "report.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(results),
                "entries": sum(v["preserved_entries"] for v in results.values()),
                "paid_calls": 0,
            }
        )
    )


async def guarded_replay():
    with (
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("Network forbidden")
        ),
        patch.object(
            socket.socket, "connect_ex", side_effect=AssertionError("Network forbidden")
        ),
    ):
        await replay()


if __name__ == "__main__":
    asyncio.run(guarded_replay())
