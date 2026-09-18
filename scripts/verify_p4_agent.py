"""Run explicitly paid P4 acceptance cases with a cumulative pre-dispatch cap."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from filelock import FileLock

from ican.agent.journal import PaidJournal
from ican.agent.schema import AgentRequest
from ican.agent.service import AgentService
from ican.api.app import load_config
from ican.retrieval.hybrid import HybridEvidenceSearchService

SWIN_CASES = {
    "lr": "swin_dev_06",
    "shape": "swin_dev_04",
    "config": "swin_dev_05",
    "motivation": "swin_dev_12",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def run(args, service=None):
    cases = {
        r["id"]: r
        for r in [
            json.loads(line)
            for line in (ROOT / "data/eval/swin_dev.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
    }
    request = AgentRequest(
        query=cases[SWIN_CASES[args.case]]["question"], collection="swin_v1"
    )
    directory = ROOT / args.run_dir
    directory.mkdir(parents=True, exist_ok=True)
    files = [
        *sorted((ROOT / "ican/agent").glob("*.py")),
        *sorted((ROOT / "ican/qa").glob("*.py")),
        *sorted((ROOT / "ican/retrieval").glob("*.py")),
        ROOT / "configs/indexing/v1.json",
        ROOT / "configs/retrieval/v1.json",
        ROOT / "configs/reranking/v1.json",
        ROOT / "configs/qa/v1.json",
        ROOT / "configs/agent/v1.json",
        ROOT / "scripts/verify_p4_agent.py",
        ROOT / "ican/api/app.py",
    ]
    identity = {
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
        "swin_questions_sha256": digest(ROOT / "data/eval/swin_dev.jsonl"),
        "frozen_test_sha256": digest(ROOT / "data/eval/swin_test.jsonl"),
    }
    if (
        identity["frozen_test_sha256"]
        != "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"
    ):
        raise ValueError("Frozen test bytes changed")
    manifest = directory / "manifest.json"
    if (
        manifest.exists()
        and json.loads(manifest.read_text(encoding="utf-8")) != identity
    ):
        raise ValueError("Acceptance source changed: select a new run directory")
    manifest.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    output = directory / f"{args.case}.json"
    if output.exists():
        print(
            json.dumps(
                {
                    "case": args.case,
                    "status": "already_recorded_no_retry",
                    "generation_calls": 0,
                }
            )
        )
        return
    marker = directory / f"{args.case}.started.json"
    if marker.exists():
        raise ValueError(
            "Case already started; inspect its retained task instead of automatically retrying"
        )
    marker.write_text(
        json.dumps({"request": request.model_dump()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if service is None:
        service = build_service()
    response = await service.run(request)
    output.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "case": args.case,
                "task_id": response.task_id,
                "status": response.status,
                "stop_reason": response.stop_reason,
                "usage": response.usage.model_dump(),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def build_service():
    index_config = load_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, index_config)
    journal = PaidJournal(ROOT / "data/processed/agent/p4-v1/paid-journal.jsonl", 40)
    return AgentService(ROOT, index_config, evidence, journal=journal)


async def main(args):
    if args.case != "all":
        await run(args)
        return
    service = build_service()
    for name in SWIN_CASES:
        await run(argparse.Namespace(case=name, run_dir=args.run_dir), service)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*SWIN_CASES, "all"], required=True)
    parser.add_argument("--run-dir", default="data/processed/evaluation/p4-smoke-v1")
    args = parser.parse_args()
    with FileLock(ROOT / "data/processed/.p4-acceptance.lock", timeout=0):
        asyncio.run(main(args))
