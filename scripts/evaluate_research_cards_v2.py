"""Prepare, run once, seal, and score the P4.6 v2 quality gate."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.research_card import collect_prior_source_ids
from ican.api.app import load_config as load_index_config
from ican.agent.journal import PaidJournal
from ican.agent.schema import BudgetExhausted, ToolInputError
from ican.evaluation.data import digest
from ican.research.auto_schema import AutoCardRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.hybrid import HybridEvidenceSearchService

DEFAULT_CONFIG = ROOT / "configs/evaluation/p46-quality-v2.json"
EXPECTED_THRESHOLDS = {
    "tool_submission_success": 0.875,
    "evidence_support_rate": 0.90,
    "field_classification_accuracy": 0.85,
    "missing_field_identification_rate": 0.85,
}
RUN_DIR = ROOT / "data/processed/evaluation/p46-quality-v2"
RUNTIME_DIR = RUN_DIR / "runtime"
FROZEN_CASES = RUNTIME_DIR / "frozen-cases.json"
CORPUS_PATH = ROOT / "data/processed/qasper_external/v1/train_corpus.jsonl"


def normalize_source_id(value: str) -> str:
    value = str(value).strip()
    return value if value.startswith("qasper:") else f"qasper:{value}"


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value, *, exclusive: bool = False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_digest(request: dict) -> str:
    encoded = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_event(path: Path, event: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with FileLock(str(path) + ".lock", timeout=5):
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def read_events(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def error_category(error: BaseException, diagnosis: dict | None = None) -> str:
    code = (diagnosis or {}).get("code", "")
    if code and code not in {"accepted", "runtime_error"}:
        return "tool_submission"
    name = type(error).__name__.lower()
    message = str(error).lower()
    if isinstance(error, BudgetExhausted):
        return "budget"
    if "timeout" in name or "timeout" in message:
        return "transport_timeout"
    if "json" in name or "schema" in message or isinstance(error, ToolInputError):
        return "json_or_schema"
    if "evidence" in message or "source" in message or "scope" in message:
        return "evidence_scope"
    if "http" in name or "connect" in name or "network" in message:
        return "transport"
    if "model" in name or "provider" in message or "service" in message:
        return "provider_or_payload"
    return "local_execution"


async def execute_cases(
    config: dict,
    frozen: dict,
    executor,
    runtime_dir: Path = RUNTIME_DIR,
):
    runtime_dir = Path(runtime_dir)
    journal_path = runtime_dir / "call-journal.jsonl"
    results_dir = runtime_dir / "case-results"
    actions_dir = runtime_dir / "raw-actions"
    results_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)
    for case in frozen["cases"]:
        key = case["key"]
        result_path = results_dir / f"{key}.json"
        if result_path.exists():
            continue
        events = read_events(journal_path)
        source_id = case["request"]["source_id"]
        source_events = [row for row in events if row.get("source_id") == source_id]
        started = [row for row in source_events if row.get("event") == "started"]
        terminal = [
            row
            for row in source_events
            if row.get("event") in {"completed", "failed", "interrupted_unknown"}
        ]
        if terminal:
            raise ValueError(f"{key}: terminal event exists without case result")
        request_sha256 = request_digest(case["request"])
        if started:
            output = {
                "status": "interrupted_unknown",
                "source_id": source_id,
                "request_sha256": request_sha256,
                "error_category": "interrupted_unknown",
                "error_type": "InterruptedCall",
                "error": "A prior started reservation has no terminal result; no retry allowed.",
                "tool_diagnosis": {
                    "status": "rejected",
                    "code": "interrupted_unknown",
                    "issues": [],
                },
                "raw_action": None,
                "usage": None,
                "response_id": None,
                "trace": None,
            }
            write_json(result_path, output, exclusive=True)
            append_event(
                journal_path,
                {
                    "event": "interrupted_unknown",
                    "source_id": source_id,
                    "request_sha256": request_sha256,
                    "model": config["model"],
                    "usage": None,
                    "response_id": None,
                    "diagnostic": "prior_started_without_terminal",
                },
            )
            continue
        if sum(row.get("event") == "started" for row in events) >= config["max_paid_calls"]:
            raise ValueError("P4.6 v2 hard paid-call cap reached")
        append_event(
            journal_path,
            {
                "event": "started",
                "source_id": source_id,
                "request_sha256": request_sha256,
                "model": config["model"],
            },
        )
        try:
            output = await executor(case)
        except BaseException as error:  # noqa: BLE001 - persist the terminal state
            output = {
                "status": "failed",
                "source_id": source_id,
                "request_sha256": request_sha256,
                "error_category": error_category(error),
                "error_type": type(error).__name__,
                "error": str(error)[:500],
                "tool_diagnosis": {
                    "status": "rejected",
                    "code": "local_executor_error",
                    "issues": [],
                },
                "raw_action": None,
                "usage": None,
                "response_id": None,
                "trace": None,
            }
        output = dict(output)
        output.setdefault("source_id", source_id)
        output.setdefault("request_sha256", request_sha256)
        raw_action = output.pop("raw_action", None)
        if raw_action is not None:
            action_path = actions_dir / f"{key}.json"
            write_json(action_path, raw_action, exclusive=True)
            output["raw_action_path"] = action_path.relative_to(runtime_dir).as_posix()
            output["raw_action_sha256"] = digest(action_path)
        else:
            output["raw_action_path"] = None
            output["raw_action_sha256"] = None
        status = output.get("status")
        if status not in {"completed", "failed"}:
            raise ValueError(f"{key}: executor returned invalid status {status!r}")
        write_json(result_path, output, exclusive=True)
        append_event(
            journal_path,
            {
                "event": status,
                "source_id": source_id,
                "request_sha256": request_sha256,
                "model": config["model"],
                "usage": output.get("usage"),
                "response_id": output.get("response_id"),
                "diagnostic": (output.get("tool_diagnosis") or {}).get("code"),
                "error_category": output.get("error_category"),
            },
        )


def matching_trace(before: set[Path]) -> Path | None:
    created = set((RUNTIME_DIR / "traces").glob("*.json")) - before
    return created.pop() if len(created) == 1 else None


async def real_executor(auto: ResearchAutoService, case: dict) -> dict:
    before = set((RUNTIME_DIR / "traces").glob("*.json"))
    card = None
    caught = None
    try:
        card = await auto.auto_card(AutoCardRequest.model_validate(case["request"]))
    except BaseException as error:  # noqa: BLE001 - trace contains the model action
        caught = error
    trace_path = matching_trace(before)
    trace = read_json(trace_path) if trace_path else {}
    records = trace.get("model_records") or []
    record = records[0] if records else {}
    diagnosis = trace.get("submission_diagnostic") or {
        "status": "rejected",
        "code": "missing_trace",
        "issues": [],
    }
    output = {
        "status": "completed" if caught is None else "failed",
        "raw_action": trace.get("model_action"),
        "trace": trace_path.name if trace_path else None,
        "trace_sha256": digest(trace_path) if trace_path else None,
        "usage": (
            card.usage.model_dump(mode="json") if card is not None else record.get("usage")
        ),
        "response_id": record.get("response_id"),
        "tool_diagnosis": diagnosis,
    }
    if caught is not None:
        output.update(
            error_category=error_category(caught, diagnosis),
            error_type=type(caught).__name__,
            error=str(caught)[:500],
        )
    return output


async def run(config_path: Path = DEFAULT_CONFIG):
    config = load_contract(config_path)
    if not FROZEN_CASES.exists():
        raise ValueError("Prepare and commit the frozen cases before running")
    frozen = read_json(FROZEN_CASES)
    if frozen["config_sha256"] != digest(config_path.resolve()):
        raise ValueError("Frozen config hash differs")
    auto = services(config, paid=True)

    async def invoke(case):
        return await real_executor(auto, case)

    await execute_cases(config, frozen, invoke, RUNTIME_DIR)


async def dry_run(config: dict):
    frozen = {
        "cases": [
            {
                "key": case["key"],
                "request": {
                    "query": case["query"],
                    "collection": config["collection"],
                    "source_id": case["source_id"],
                },
            }
            for case in config["cases"]
        ]
    }

    async def fake(case):
        return {
            "status": "completed",
            "raw_action": {"dry_run": True, "source_id": case["request"]["source_id"]},
            "trace": None,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "response_id": None,
            "tool_diagnosis": {"status": "accepted", "code": "accepted", "issues": []},
        }

    with tempfile.TemporaryDirectory(prefix="ican-p46-v2-") as directory:
        target = Path(directory)
        await execute_cases(config, frozen, fake, target)
        results = list((target / "case-results").glob("*.json"))
        events = read_events(target / "call-journal.jsonl")
        if len(results) != 8 or sum(row["event"] == "started" for row in events) != 8:
            raise ValueError("Dry-run persistence verification failed")
    return {"status": "dry_run_passed", "cases": 8}


def source_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def assert_clean_source_tree():
    output = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    )
    runtime_prefix = RUNTIME_DIR.relative_to(ROOT).as_posix() + "/"
    dirty = []
    for line in output.splitlines():
        path = line[3:].strip().replace("\\", "/")
        if not path.startswith(runtime_prefix):
            dirty.append(path)
    if dirty:
        raise ValueError(f"Source tree must be clean before prepare: {dirty[:8]}")


def source_hashes(config_path: Path) -> dict[str, str]:
    paths = [
        config_path,
        ROOT / "configs/agent/v2.json",
        ROOT / "configs/chunking/v1.json",
        ROOT / "configs/indexing/v1.json",
        ROOT / "ican/research/auto_schema.py",
        ROOT / "ican/research/auto_service.py",
        ROOT / "ican/research/field_rules.py",
        ROOT / "ican/research/submission.py",
        ROOT / "ican/agent/runtime.py",
        ROOT / "ican/evaluation/research_card.py",
        ROOT / "ican/evaluation/research_audit.py",
        ROOT / "scripts/evaluate_research_cards_v2.py",
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def services(config: dict, *, paid: bool = False) -> ResearchAutoService:
    index_config = load_index_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, index_config)
    research = ResearchService(
        ROOT,
        index_config,
        evidence,
        store=ResearchStore(RUNTIME_DIR / "records"),
    )
    kwargs = {"trace_directory": RUNTIME_DIR / "traces"}
    if paid:
        kwargs["journal"] = PaidJournal(
            RUNTIME_DIR / "paid-journal.jsonl", config["max_paid_calls"]
        )
    auto = ResearchAutoService(ROOT, index_config, evidence, research, **kwargs)
    auto.config.answer_model = config["model"]
    return auto


def validate_contract(config: dict, *, prior_source_ids: set[str]) -> dict:
    value = copy.deepcopy(config)
    cases = value.get("cases", [])
    if len(cases) != 8:
        raise ValueError("P4.6 v2 requires exactly eight cases")
    for case in cases:
        case["source_id"] = normalize_source_id(case.get("source_id", ""))
    ids = [case["source_id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("P4.6 v2 cases must use distinct source IDs")
    if value.get("split") != "train":
        raise ValueError("P4.6 v2 split must be train")
    if value.get("model") != "deepseek-v4-pro":
        raise ValueError("P4.6 v2 model must be deepseek-v4-pro")
    if value.get("max_paid_calls") != 8:
        raise ValueError("P4.6 v2 paid call cap must be eight")
    if value.get("retry_limit") != 0:
        raise ValueError("P4.6 v2 retry limit must be zero")
    if value.get("thresholds") != EXPECTED_THRESHOLDS:
        raise ValueError("P4.6 v2 quality thresholds differ from the frozen contract")
    prior = {normalize_source_id(item) for item in prior_source_ids}
    overlap = sorted(set(ids) & prior)
    if overlap:
        raise ValueError(f"Quality cases were used by prior runs: {overlap}")
    return value


def load_contract(path: Path = DEFAULT_CONFIG) -> dict:
    prior = collect_prior_source_ids(
        [
            ROOT / "data/processed/evaluation",
            ROOT / "data/processed/research",
        ]
    )
    return validate_contract(read_json(path), prior_source_ids=prior)


def prepare(config_path: Path = DEFAULT_CONFIG):
    assert_clean_source_tree()
    config_path = config_path.resolve()
    config = load_contract(config_path)
    if FROZEN_CASES.exists():
        raise ValueError("P4.6 v2 frozen cases already exist")
    auto = services(config)
    cases = []
    fingerprints = set()
    for configured in config["cases"]:
        request = AutoCardRequest(
            query=configured["query"],
            collection=config["collection"],
            source_id=configured["source_id"],
        )
        candidate, fingerprint = auto._paper_evidence(request)
        if candidate.title != configured["title"]:
            raise ValueError(f"{configured['key']}: title differs from the corpus")
        if len(candidate.evidence) != 6:
            raise ValueError(f"{configured['key']}: expected six evidence items")
        ids = [item.chunk_id for item in candidate.evidence]
        if len(set(ids)) != 6 or any(not item.text.strip() for item in candidate.evidence):
            raise ValueError(f"{configured['key']}: invalid frozen evidence")
        fingerprints.add(fingerprint)
        cases.append(
            {
                "key": configured["key"],
                "request": request.model_dump(mode="json"),
                "title": candidate.title,
                "source_path": candidate.source_path,
                "source_version": candidate.source_version,
                "index_fingerprint": fingerprint,
                "evidence": [item.model_dump(mode="json") for item in candidate.evidence],
                "evidence_sha256": {
                    item.chunk_id: text_digest(item.text) for item in candidate.evidence
                },
            }
        )
    if len(fingerprints) != 1:
        raise ValueError("Frozen papers resolved against different indexes")
    payload = {
        "version": config["version"],
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit(),
        "model": config["model"],
        "max_paid_calls": config["max_paid_calls"],
        "retry_limit": config["retry_limit"],
        "thresholds": config["thresholds"],
        "config_sha256": digest(config_path),
        "corpus_sha256": digest(CORPUS_PATH),
        "corpus_manifest_sha256": digest(
            ROOT / "data/processed/qasper_external/v1/manifest.json"
        ),
        "index_fingerprint": next(iter(fingerprints)),
        "source_sha256": source_hashes(config_path),
        "cases": cases,
    }
    write_json(FROZEN_CASES, payload, exclusive=True)
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["prepare", "preflight", "run", "seal", "audit", "finalize"]
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_contract(args.config)
    if args.command == "prepare":
        payload = prepare(args.config)
        print(
            json.dumps(
                {"status": "prepared", "cases": len(payload["cases"]), "path": str(FROZEN_CASES)},
                ensure_ascii=False,
            )
        )
        return
    if args.command == "run":
        if args.dry_run:
            print(json.dumps(asyncio.run(dry_run(config))))
        else:
            asyncio.run(run(args.config))
            print(json.dumps({"status": "run_complete"}))
        return
    if args.command != "preflight":
        raise SystemExit(f"{args.command} is not implemented yet")
    print(json.dumps({"status": "contract_valid", "cases": len(config["cases"])}))


if __name__ == "__main__":
    main()
