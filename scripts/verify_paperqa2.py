"""Functional smoke cases, never a frozen-test accuracy evaluation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.api.app import create_app, load_config
from ican.qa.prompts import QA, SYSTEM
from ican.qa.schema import QAConfig
from ican.qa.service import QAService
from ican.retrieval.service import EvidenceSearchService


class OfflineModel:
    name = "fake-offline-interface-smoke"
    calls = 0

    async def call_single(self, *, messages, **kwargs):
        from lmi import LLMResult

        self.calls += 1
        cid = re.search(r"pqac-[a-z0-9]{8}", messages[1].content)[0]
        return LLMResult(
            text=f"离线接口样例，仅验证引用映射 ({cid})。",
            model=self.name,
            prompt_count=0,
            completion_count=0,
        )


async def run(live: bool, selected_case: str):
    import httpx
    from paperqa import Settings

    evidence = EvidenceSearchService(ROOT, load_config(ROOT))
    config = QAConfig.model_validate_json(
        (ROOT / "configs/qa/v1.json").read_text(encoding="utf-8")
    )
    qa = QAService(ROOT, evidence, config, None if live else OfflineModel)
    app = create_app(root=ROOT, service=evidence, qa_service=qa)
    cases = [
        {
            "query": "Swin Transformer 为什么使用 shifted window？它如何让相邻窗口交换信息？",
            "collection": "swin_v1",
            "filters": {"source_types": ["paper"]},
        },
        {
            "query": "官方 swin_tiny_patch4_window7_224.yaml 中 EMBED_DIM、DEPTHS、NUM_HEADS 和 WINDOW_SIZE 分别是什么？",
            "collection": "swin_v1",
            "filters": {
                "source_types": ["config"],
                "path_prefixes": [
                    "data/raw/repositories/Swin-Transformer/configs/swin/swin_tiny_patch4_window7_224.yaml"
                ],
            },
        },
    ]
    outputs = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for case_name, case in zip(["paper", "config"], cases, strict=True):
            if selected_case != "all" and selected_case != case_name:
                continue
            started = perf_counter()
            result = await client.post("/v1/qa/answer", json=case)
            # Only sanitized HTTP details or schema output can enter this record.
            outputs.append(
                {
                    "request": case,
                    "case": case_name,
                    "elapsed_seconds": perf_counter() - started,
                    "http_status": result.status_code,
                    "response": result.json(),
                }
            )
            print(
                json.dumps(
                    {
                        "http_status": result.status_code,
                        "status": result.json().get("status"),
                        "usage": result.json().get("usage"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    directory = ROOT / "data/processed/qa"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "mode": "live" if live else "offline-fake-LLM",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "qa_config": config.model_dump(),
        "prompt_sha256": hashlib.sha256((SYSTEM + QA).encode()).hexdigest(),
        "cases": outputs,
        "upstream_reference_settings": Settings().model_dump(mode="json"),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{'live' if live else 'offline'}-{selected_case}-{stamp}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {path}")
    if any(
        x["http_status"] != 200
        or x["response"].get("status") not in {"answered", "review_required"}
        for x in outputs
    ):
        raise SystemExit("Functional acceptance failed; inspect sanitized smoke record")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="One generation call per selected case, max1536tokens each",
    )
    parser.add_argument("--case", choices=["all", "paper", "config"], default="all")
    args = parser.parse_args()
    asyncio.run(run(args.live, args.case))
