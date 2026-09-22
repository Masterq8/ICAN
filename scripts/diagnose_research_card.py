"""Single new train-paper diagnostic after three untraced card rejections."""

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
from ican.evaluation.p4_agent import write_manifest
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.research.auto_schema import AutoCardRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.hybrid import HybridEvidenceSearchService

DIRECTORY = ROOT / "data/processed/evaluation/p46-card-diagnostic-v1"
REQUEST = AutoCardRequest(
    query="semantic parsing paraphrase generation model dataset evaluation",
    collection="qasper_train_v1",
    source_id="qasper:1601.06068",
)


async def run():
    identity = {
        "version": "p46-card-diagnostic-v1",
        "max_paid_calls": 1,
        "request": REQUEST.model_dump(mode="json"),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path)
            for path in [
                ROOT / "ican/research/auto_schema.py",
                ROOT / "ican/research/auto_service.py",
                ROOT / "ican/research/service.py",
                ROOT / "ican/agent/runtime.py",
                ROOT / "configs/agent/v2.json",
                ROOT / "configs/indexing/v1.json",
                ROOT / "scripts/diagnose_research_card.py",
            ]
        },
    }
    write_manifest(DIRECTORY, identity)
    if (DIRECTORY / "started.json").exists():
        raise ValueError("Diagnostic already started; no retry")
    config = load_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, config)
    research = ResearchService(
        ROOT, config, evidence, store=ResearchStore(DIRECTORY / "records")
    )
    auto = ResearchAutoService(
        ROOT,
        config,
        evidence,
        research,
        journal=PaidJournal(DIRECTORY / "paid-journal.jsonl", 1),
        trace_directory=DIRECTORY / "tasks",
    )
    (DIRECTORY / "started.json").write_text(
        REQUEST.model_dump_json(indent=2), encoding="utf-8"
    )
    try:
        result = await auto.auto_card(REQUEST)
        (DIRECTORY / "response.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        outcome = {
            "status": "completed",
            "response_sha256": digest(DIRECTORY / "response.json"),
        }
    except (ValueError, RuntimeError, ModelTimeout, ModelUnavailable) as error:
        outcome = {
            "status": "failed",
            "error_type": type(error).__name__,
            "error_detail": str(error)[:1000],
        }
    outcome["manifest_sha256"] = digest(DIRECTORY / "manifest.json")
    outcome["journal_sha256"] = digest(DIRECTORY / "paid-journal.jsonl")
    (DIRECTORY / "summary.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(outcome, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    with FileLock(ROOT / "data/processed/.p46-card-diagnostic.lock", timeout=0):
        asyncio.run(run())
