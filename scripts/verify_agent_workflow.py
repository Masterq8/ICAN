"""Run two development-only verified-workflow cases under a new eight-call cap."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.agent.schema import AgentConfig, AgentRequest
from ican.agent.service import AgentService
from ican.api.app import load_config
from ican.evaluation.data import digest, read_jsonl
from ican.evaluation.p4_agent import FROZEN_SHA256, write_manifest
from ican.retrieval.hybrid import HybridEvidenceSearchService

CASES = {
    "shape": ("swin_dev_04", "code_execution"),
    "motivation": ("swin_dev_12", "inference"),
}


async def run(directory: Path):
    config = AgentConfig.model_validate_json(
        (ROOT / "configs/agent/v2.json").read_text(encoding="utf-8")
    )
    frozen = digest(ROOT / "data/eval/swin_test.jsonl")
    if frozen != FROZEN_SHA256:
        raise ValueError("Frozen test bytes changed")
    dev = {item["id"]: item for item in read_jsonl(ROOT / "data/eval/swin_dev.jsonl")}
    requests = {
        name: AgentRequest(
            query=dev[case_id]["question"],
            collection="swin_v1",
            family="swin_v1",
            required_claim_kinds=[kind],
        )
        for name, (case_id, kind) in CASES.items()
    }
    files = [
        *sorted((ROOT / "ican/agent").glob("*.py")),
        *sorted((ROOT / "ican/research").glob("*.py")),
        *sorted((ROOT / "ican/qa").glob("*.py")),
        *sorted((ROOT / "ican/retrieval").glob("*.py")),
        ROOT / "configs/agent/v2.json",
        ROOT / "configs/indexing/v1.json",
        ROOT / "configs/retrieval/v1.json",
        ROOT / "configs/reranking/v1.json",
        ROOT / "configs/qa/v1.json",
        ROOT / "scripts/verify_agent_workflow.py",
    ]
    identity = {
        "version": "p4-verified-acceptance-v1",
        "max_paid_calls": 8,
        "frozen_test_sha256": frozen,
        "development_sha256": digest(ROOT / "data/eval/swin_dev.jsonl"),
        "agent_config": config.model_dump(),
        "requests": {name: request.model_dump() for name, request in requests.items()},
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in files
        },
    }
    write_manifest(directory, identity)
    # Check all case markers before initializing any paid runtime.
    for name in requests:
        if (directory / f"{name}.json").exists() or (
            directory / f"{name}.started.json"
        ).exists():
            raise ValueError(
                "Verified acceptance already started; automatic retry is disabled"
            )
    index_config = load_config(ROOT)
    service = AgentService(
        ROOT,
        index_config,
        HybridEvidenceSearchService(ROOT, index_config),
        config=config,
        journal=PaidJournal(directory / "paid-journal.jsonl", 8),
    )
    results = {}
    for name, request in requests.items():
        (directory / f"{name}.started.json").write_text(
            request.model_dump_json(indent=2), encoding="utf-8"
        )
        response = await service.run(request)
        (directory / f"{name}.json").write_text(
            response.model_dump_json(indent=2), encoding="utf-8"
        )
        results[name] = response.model_dump(mode="json")
        print(
            json.dumps(
                {
                    "case": name,
                    "task_id": response.task_id,
                    "status": response.status,
                    "usage": response.usage.model_dump(),
                    "stages": response.workflow_stages,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    summary = {
        "run": "p4-v3",
        "manifest_sha256": digest(directory / "manifest.json"),
        "journal_sha256": digest(directory / "paid-journal.jsonl"),
        "paid_calls": sum(result["usage"]["paid_calls"] for result in results.values()),
        "results": {
            name: {
                "task_id": result["task_id"],
                "status": result["status"],
                "workflow_stages": result["workflow_stages"],
                "usage": result["usage"],
            }
            for name, result in results.items()
        },
        "actual_cost_usd": None,
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default="data/processed/evaluation/p4-v3")
    args = parser.parse_args()
    with FileLock(ROOT / "data/processed/.p4-v3-acceptance.lock", timeout=0):
        asyncio.run(run(ROOT / args.run_dir))
