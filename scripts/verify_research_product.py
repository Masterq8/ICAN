"""Three fresh paper-card smoke cases; one Flash call each, no retries."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.api.app import load_config
from ican.evaluation.data import digest
from ican.evaluation.p4_agent import FROZEN_SHA256, write_manifest
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.research.auto_schema import AutoCardRequest, ComparisonRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.hybrid import HybridEvidenceSearchService

DIRECTORY = ROOT / "data/processed/evaluation/p46-product-smoke-v1"
CASES = {
    "swin": AutoCardRequest(
        query="Swin Transformer image classification training dataset input size and top-1 accuracy",
        collection="swin_v1",
        source_id="src:21e757794f07f8f043ac",
    ),
    "qa_modules": AutoCardRequest(
        query="question answering model evaluation dataset and result",
        collection="qasper_train_v1",
        source_id="qasper:1601.01705",
    ),
    "qa_memory": AutoCardRequest(
        query="question answering model evaluation dataset and result",
        collection="qasper_train_v1",
        source_id="qasper:1603.01417",
    ),
}


async def run():
    if digest(ROOT / "data/eval/swin_test.jsonl") != FROZEN_SHA256:
        raise ValueError("Frozen test bytes changed")
    files = [
        *sorted((ROOT / "ican/agent").glob("*.py")),
        *sorted((ROOT / "ican/research").glob("*.py")),
        *sorted((ROOT / "ican/retrieval").glob("*.py")),
        ROOT / "ican/api/app.py",
        ROOT / "configs/agent/v2.json",
        ROOT / "configs/indexing/v1.json",
        ROOT / "configs/retrieval/v1.json",
        ROOT / "configs/reranking/v1.json",
        ROOT / "scripts/verify_research_product.py",
    ]
    identity = {
        "version": "p46-product-smoke-v1",
        "max_paid_calls": 3,
        "frozen_test_sha256": FROZEN_SHA256,
        "cases": {name: req.model_dump(mode="json") for name, req in CASES.items()},
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in files
        },
    }
    write_manifest(DIRECTORY, identity)
    if any((DIRECTORY / f"{name}.started.json").exists() for name in CASES):
        raise ValueError("Product smoke already started; no automatic retry")
    config = load_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, config)
    research = ResearchService(
        ROOT,
        config,
        evidence,
        store=ResearchStore(DIRECTORY / "records"),
    )
    auto = ResearchAutoService(
        ROOT,
        config,
        evidence,
        research,
        journal=PaidJournal(DIRECTORY / "paid-journal.jsonl", 3),
    )
    outputs = {}
    for name, request in CASES.items():
        (DIRECTORY / f"{name}.started.json").write_text(
            request.model_dump_json(indent=2), encoding="utf-8"
        )
        try:
            card = await auto.auto_card(request)
            (DIRECTORY / f"{name}.json").write_text(
                card.model_dump_json(indent=2), encoding="utf-8"
            )
            outputs[name] = {
                "status": "completed",
                "screening_statuses": [v.status for v in card.screening.claims],
                "field_statuses": {
                    field.name: field.claims[0].status
                    for field in card.extraction.fields
                }
                if card.extraction
                else {},
                "record_id": str(card.extraction.record_id)
                if card.extraction
                else None,
                "response_sha256": digest(DIRECTORY / f"{name}.json"),
            }
        except (ValueError, RuntimeError, ModelTimeout, ModelUnavailable) as error:
            outputs[name] = {"status": "failed", "error_type": type(error).__name__}
        print(
            json.dumps({"case": name, **outputs[name]}, ensure_ascii=False), flush=True
        )
    pair = [outputs[name].get("record_id") for name in ("qa_modules", "qa_memory")]
    comparison = None
    if all(pair):
        report = auto.compare(ComparisonRequest(record_ids=pair))
        (DIRECTORY / "comparison.md").write_text(report.markdown, encoding="utf-8")
        comparison = {
            "comparable": report.comparable,
            "warnings": report.warnings,
            "markdown_sha256": digest(DIRECTORY / "comparison.md"),
        }
    summary = {
        "run": "p46-product-smoke-v1",
        "manifest_sha256": digest(DIRECTORY / "manifest.json"),
        "journal_sha256": digest(DIRECTORY / "paid-journal.jsonl"),
        "cases": outputs,
        "comparison": comparison,
        "actual_cost_usd": None,
    }
    (DIRECTORY / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    with FileLock(ROOT / "data/processed/.p46-product-smoke.lock", timeout=0):
        asyncio.run(run())
