"""Run and audit the fixed, separately budgeted P4.4 Agent regression."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.agent.schema import AgentConfig
from ican.agent.service import AgentService
from ican.api.app import load_config
from ican.evaluation.p4_agent import (
    P4AgentEvaluationRunner,
    audit_run,
    build_p44_cases,
)
from ican.retrieval.hybrid import HybridEvidenceSearchService

MAX_CALLS = 32
RUN_DIR = "data/processed/evaluation/p4-v2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_identity() -> tuple[list, dict]:
    cases, identity = build_p44_cases(ROOT)
    source_files = [
        *sorted((ROOT / "ican/agent").glob("*.py")),
        *sorted((ROOT / "ican/research").glob("*.py")),
        ROOT / "ican/evaluation/p4_agent.py",
        ROOT / "ican/api/app.py",
        ROOT / "configs/agent/v1.json",
        ROOT / "configs/indexing/v1.json",
        ROOT / "configs/retrieval/v1.json",
        ROOT / "configs/reranking/v1.json",
        ROOT / "configs/qa/v1.json",
        ROOT / "scripts/evaluate_p4_agent.py",
    ]
    return cases, {
        **identity,
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in source_files
        },
    }


def build_service(directory: Path) -> AgentService:
    index_config = load_config(ROOT)
    base = AgentConfig.model_validate_json(
        (ROOT / "configs/agent/v1.json").read_text(encoding="utf-8")
    )
    config = base.model_copy(update={"max_planner_calls": 3, "max_tool_calls": 8})
    return AgentService(
        ROOT,
        index_config,
        HybridEvidenceSearchService(ROOT, index_config),
        config=config,
        journal=PaidJournal(Path(directory) / "paid-journal.jsonl", MAX_CALLS),
    )


async def run_cases(args) -> int:
    directory = ROOT / args.run_dir
    cases, identity = run_identity()
    runner = P4AgentEvaluationRunner(
        directory, cases, identity, build_service(directory)
    )
    selected = (
        cases
        if args.case == "all"
        else [case for case in cases if case.key == args.case]
    )
    if not selected:
        raise ValueError("Unknown fixed P4.4 case")
    for case in selected:
        response = await runner.run_case(case)
        print(
            json.dumps(
                {
                    "case": case.key,
                    "task_id": response.task_id,
                    "status": response.status,
                    "stop_reason": response.stop_reason,
                    "usage": response.usage.model_dump(),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return 0


def audit(args) -> int:
    directory = ROOT / args.run_dir
    cases, identity = run_identity()
    report = audit_run(directory, cases, identity, max_calls=MAX_CALLS)
    (directory / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["status"] == "passed" else 1


def main(args) -> int:
    with FileLock(ROOT / "data/processed/.p4-v2-evaluation.lock", timeout=0):
        if args.command == "run":
            return asyncio.run(run_cases(args))
        return audit(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "audit"])
    parser.add_argument("--case", default="all")
    parser.add_argument("--run-dir", default=RUN_DIR)
    raise SystemExit(main(parser.parse_args()))
