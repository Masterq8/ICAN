"""One new Swin research question under a separate four-call verified budget."""

from __future__ import annotations

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
from ican.evaluation.data import digest
from ican.evaluation.p4_agent import FROZEN_SHA256, write_manifest
from ican.retrieval.hybrid import HybridEvidenceSearchService

DIRECTORY = ROOT / "data/processed/evaluation/p4-v4-research"
REQUEST = AgentRequest(
    query=(
        "只根据固定Swin Transformer官方仓库中PatchMerging.forward的源码，"
        "当输入特征x的L=64且input_resolution=(8,8)时，两个assert是否允许继续？"
        "请给出原始代码行号，明确这是静态前置条件检查，不要声称已执行完整模型。"
    ),
    collection="swin_v1",
    family="swin_v1",
    required_claim_kinds=["code_execution"],
)


async def run():
    config_path = ROOT / "configs/agent/v2.json"
    config = AgentConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    frozen = digest(ROOT / "data/eval/swin_test.jsonl")
    if frozen != FROZEN_SHA256:
        raise ValueError("Frozen test bytes changed")
    files = [
        *sorted((ROOT / "ican/agent").glob("*.py")),
        *sorted((ROOT / "ican/research").glob("*.py")),
        *sorted((ROOT / "ican/qa").glob("*.py")),
        *sorted((ROOT / "ican/retrieval").glob("*.py")),
        config_path,
        ROOT / "configs/indexing/v1.json",
        ROOT / "configs/retrieval/v1.json",
        ROOT / "configs/reranking/v1.json",
        ROOT / "configs/qa/v1.json",
        ROOT / "scripts/verify_agent_research_v4.py",
    ]
    identity = {
        "version": "p4-v4-research-v1",
        "case": "patch_merging_even_8x8",
        "new_question_not_previous_development_case": True,
        "max_paid_calls": 4,
        "frozen_test_sha256": frozen,
        "prior_failed_manifest_sha256": digest(
            ROOT / "data/processed/evaluation/p4-v3/manifest.json"
        ),
        "neutral_protocol_result_sha256": digest(
            ROOT / "data/processed/evaluation/p4-v4-protocol/result.json"
        ),
        "agent_config": config.model_dump(mode="json"),
        "request": REQUEST.model_dump(mode="json"),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in files
        },
    }
    write_manifest(DIRECTORY, identity)
    if (DIRECTORY / "started.json").exists() or (DIRECTORY / "response.json").exists():
        raise ValueError("Research run already started; no automatic retry")
    index_config = load_config(ROOT)
    service = AgentService(
        ROOT,
        index_config,
        HybridEvidenceSearchService(ROOT, index_config),
        config=config,
        journal=PaidJournal(DIRECTORY / "paid-journal.jsonl", 4),
    )
    service.task_directory = DIRECTORY
    (DIRECTORY / "started.json").write_text(
        REQUEST.model_dump_json(indent=2), encoding="utf-8"
    )
    response = await service.run(REQUEST)
    (DIRECTORY / "response.json").write_text(
        response.model_dump_json(indent=2), encoding="utf-8"
    )
    verdicts = [
        verdict
        for artifact in response.artifacts
        if artifact.get("kind") == "claim_verification"
        for verdict in artifact.get("verdicts", [])
    ]
    summary = {
        "case": identity["case"],
        "task_id": response.task_id,
        "status": response.status,
        "stop_reason": response.stop_reason,
        "workflow_stages": response.workflow_stages,
        "claim_statuses": [verdict["status"] for verdict in verdicts],
        "usage": response.usage.model_dump(mode="json"),
        "answer_present": response.answer is not None,
        "actual_cost_usd": None,
        "manifest_sha256": digest(DIRECTORY / "manifest.json"),
        "journal_sha256": digest(DIRECTORY / "paid-journal.jsonl"),
        "response_sha256": digest(DIRECTORY / "response.json"),
    }
    (DIRECTORY / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": response.status,
                "paid_calls": response.usage.paid_calls,
                "claim_statuses": summary["claim_statuses"],
                "answer_present": summary["answer_present"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    with FileLock(ROOT / "data/processed/.p4-v4-research.lock", timeout=0):
        asyncio.run(run())
