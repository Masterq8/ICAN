"""One neutral real call to distinguish SDK named-tool request from provider behavior."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.agent.runtime import DeepSeekRuntime, tool_options
from ican.agent.schema import AgentConfig, BudgetExhausted
from ican.evaluation.data import digest
from ican.evaluation.p4_agent import write_manifest
from ican.qa.runtime import ModelTimeout, ModelUnavailable

DIRECTORY = ROOT / "data/processed/evaluation/p4-v4-protocol"
TOOL = {
    "type": "function",
    "function": {
        "name": "submit_token",
        "description": "Return the exact neutral token requested by the user.",
        "parameters": {
            "type": "object",
            "properties": {"token": {"type": "string", "const": "ok"}},
            "required": ["token"],
            "additionalProperties": False,
        },
    },
}
MESSAGES = [
    {"role": "system", "content": "Only call the provided submit_token function."},
    {"role": "user", "content": "Submit the exact token ok."},
]


async def run():
    config_path = ROOT / "configs/agent/v2.json"
    config = AgentConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    identity = {
        "version": "p4-v4-neutral-protocol-v1",
        "max_paid_calls": 1,
        "model": config.planner_model,
        "messages": MESSAGES,
        "tools": [TOOL],
        "sdk_options": tool_options([TOOL]),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path)
            for path in [
                ROOT / "ican/agent/runtime.py",
                ROOT / "ican/agent/journal.py",
                config_path,
                ROOT / "scripts/verify_agent_tool_protocol.py",
            ]
        },
    }
    write_manifest(DIRECTORY, identity)
    if (DIRECTORY / "started.json").exists():
        raise ValueError("Neutral protocol run already started; no automatic retry")
    (DIRECTORY / "started.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    runtime = DeepSeekRuntime(
        ROOT, config, PaidJournal(DIRECTORY / "paid-journal.jsonl", 1), "neutral"
    )
    outcome = {"status": "failed", "model": config.planner_model}
    try:
        action = await runtime.plan(MESSAGES, [TOOL])
        calls = action.get("tool_calls", [])
        names = [item["function"]["name"] for item in calls]
        arguments = [json.loads(item["function"]["arguments"]) for item in calls]
        outcome.update(
            {
                "status": "passed"
                if len(calls) == 1
                and names == ["submit_token"]
                and arguments == [{"token": "ok"}]
                else "provider_tool_choice_mismatch",
                "returned_tool_names": names,
                "returned_arguments": arguments,
            }
        )
    except (BudgetExhausted, ModelTimeout, ModelUnavailable, ValueError) as error:
        outcome["error_type"] = type(error).__name__
    outcome.update(
        {
            "records": runtime.records,
            "manifest_sha256": digest(DIRECTORY / "manifest.json"),
            "journal_sha256": digest(DIRECTORY / "paid-journal.jsonl"),
        }
    )
    (DIRECTORY / "result.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": outcome["status"], "calls": len(runtime.records)}))


if __name__ == "__main__":
    with FileLock(ROOT / "data/processed/.p4-v4-protocol.lock", timeout=0):
        asyncio.run(run())
