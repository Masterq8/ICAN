"""One frozen P6 run: preflight, 120 no-retry attempts, then offline scoring."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from dotenv import load_dotenv
from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.agent.schema import AgentConfig, AgentRequest, AgentResponse
from ican.agent.service import AgentService
from ican.api.app import load_config
from ican.evaluation.data import Case, digest, read_jsonl
from ican.evaluation.metrics import (
    answer_for_official_score,
    qasper_references,
    score_qasper_retrieval,
    score_swin,
    unit_coverage,
)
from ican.qa.prompts import INSUFFICIENT
from ican.qa.schema import QARequest, QAResponse
from ican.qa.service import QAService
from ican.retrieval.hybrid import HybridEvidenceSearchService
from ican.retrieval.schema import SearchRequest, SearchResponse
from ican.retrieval.service import EvidenceSearchService
from third_party.qasper.evaluator import evaluate

RUN_DIR = ROOT / "data/processed/evaluation/p6-v1"
SWIN_TEST = "data/eval/swin_test.jsonl"
QASPER_VALIDATION = "data/eval/qasper_external/v1/validation_questions.jsonl"
FROZEN_SWINT_SHA256 = "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"
FROZEN_QASPER_SHA256 = (
    "21ecb3df1c226997c999e786882ae22b3620e405f324b5ac8e95de7562c3f761"
)
MODEL = "deepseek-v4-pro"
STRATEGIES = ("dense", "hybrid_rerank", "agent")
MAX_QA_ATTEMPTS = 80
MAX_AGENT_CALLS = 160


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _append(path: Path, value: dict) -> None:
    from ican.evaluation.runner import append_record

    append_record(path, value)


def _repo_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _source_files() -> list[Path]:
    fixed = [
        ROOT / name
        for name in [
            SWIN_TEST,
            QASPER_VALIDATION,
            "data/eval/swin_evidence.json",
            "data/eval/swin_eval_manifest.json",
            "configs/indexing/v2.json",
            "configs/retrieval/v1.json",
            "configs/reranking/v1.json",
            "configs/qa/v1.json",
            "configs/agent/v2.json",
            "scripts/run_p6_frozen.py",
            "third_party/qasper/evaluator.py",
        ]
    ]
    for folder in (
        "ican/qa",
        "ican/retrieval",
        "ican/agent",
        "ican/evaluation",
        "ican/research",
        "ican/indexing",
    ):
        fixed.extend(sorted((ROOT / folder).glob("*.py")))
    return sorted(set(fixed))


def _identity() -> dict:
    if digest(ROOT / SWIN_TEST) != FROZEN_SWINT_SHA256:
        raise ValueError("Swin frozen bytes changed")
    if digest(ROOT / QASPER_VALIDATION) != FROZEN_QASPER_SHA256:
        raise ValueError("QASPER validation bytes changed")
    service = EvidenceSearchService(ROOT, load_config(ROOT))
    directory, index_manifest = service._load_index()
    return {
        "version": "p6-frozen-once-v1",
        "git_commit": _repo_commit(),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in _source_files()
        },
        "index_fingerprint": directory.name,
        "index_manifest_sha256": digest(directory / "index_manifest.json"),
        "index_identity": index_manifest["identity"],
        "cases": {"swin_test": 8, "qasper_validation": 32},
        "strategies": list(STRATEGIES),
        "retrieval_k": 8,
        "models": {"qa": MODEL, "agent_planner": MODEL, "agent_answer": MODEL},
        "budgets": {
            "qa_attempts": MAX_QA_ATTEMPTS,
            "agent_paid_calls": MAX_AGENT_CALLS,
        },
        "policy": "started attempts never retried; frozen results never used to tune",
    }


def _manifest() -> dict:
    path = RUN_DIR / "manifest.json"
    if not path.exists():
        raise ValueError(
            "P6 manifest is absent; run freeze before opening frozen cases"
        )
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved["identity"] != _identity():
        raise ValueError("P6 source, index, model, or budget identity changed")
    return saved


def freeze() -> None:
    RUN_DIR.parent.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(exist_ok=True)
    path = RUN_DIR / "manifest.json"
    if path.exists():
        raise ValueError("P6 has already been frozen; refusing a second freeze")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise ValueError("Commit the P6 runner and plan before freezing")
    identity = _identity()  # Only hashes the frozen data; does not parse gold.
    _write_json(
        path,
        {"identity": identity, "frozen_at": datetime.now(timezone.utc).isoformat()},
    )
    print(f"Frozen P6: {identity['git_commit']} / {identity['index_fingerprint']}")


def _cases(*, include_gold: bool) -> tuple[list[Case], dict[str, dict]]:
    cases: list[Case] = []
    gold: dict[str, dict] = {}
    counts = {"swin": 0, "qasper": 0}
    # The execution path projects each row to public query fields immediately.
    # Gold is retained only by the post-run report path.
    for line in (ROOT / SWIN_TEST).open(encoding="utf-8"):
        if not line.strip():
            continue
        item = json.loads(line)
        counts["swin"] += 1
        case = Case(item["id"], "swin", "test", item["question"], "swin_v1", {})
        cases.append(case)
        if include_gold:
            gold[case.key] = item
    for line in (ROOT / QASPER_VALIDATION).open(encoding="utf-8"):
        if not line.strip():
            continue
        item = json.loads(line)
        counts["qasper"] += 1
        case = Case(
            item["question_id"],
            "qasper",
            "validation",
            item["question"],
            "qasper_validation_v1",
            {
                "source_types": ["paper"],
                "path_prefixes": [f"qasper/{item['paper_id']}"],
            },
        )
        cases.append(case)
        if include_gold:
            gold[case.key] = item
    if counts != {"swin": 8, "qasper": 32}:
        raise ValueError("Frozen case counts differ from the protocol")
    if len({case.key for case in cases}) != 40:
        raise ValueError("Duplicate frozen case key")
    return cases, gold


class FixedSearch:
    def __init__(self, request: SearchRequest, result: SearchResponse):
        self.request = request
        self.result = result

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.model_dump() != self.request.model_dump():
            raise ValueError("QA attempted a different retrieval request")
        return self.result


async def execute() -> None:
    _manifest()
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("ICAN_LLM_API_KEY"):
        raise ValueError("ICAN_LLM_API_KEY is not configured")
    if os.environ.get("ICAN_LLM_PROVIDER") != "openai":
        raise ValueError("OpenAI-compatible model provider is not configured")
    if os.environ.get("ICAN_LLM_BASE_URL") != "https://api.deepseek.com":
        raise ValueError("DeepSeek OpenAI-compatible base URL is not configured")
    os.environ["ICAN_LLM_MODEL"] = MODEL
    cases, _ = _cases(include_gold=False)
    service = HybridEvidenceSearchService(ROOT, load_config(ROOT))
    agent_config = AgentConfig.model_validate_json(
        (ROOT / "configs/agent/v2.json").read_text(encoding="utf-8")
    ).model_copy(update={"answer_model": MODEL})
    agent = AgentService(
        ROOT,
        load_config(ROOT),
        service,
        config=agent_config,
        journal=PaidJournal(RUN_DIR / "agent-paid-journal.jsonl", MAX_AGENT_CALLS),
    )
    agent.task_directory = RUN_DIR / "agent-tasks"
    journal_path = RUN_DIR / "attempts.jsonl"
    attempts = read_jsonl(journal_path) if journal_path.exists() else []
    started = {row["key"] for row in attempts if row["event"] == "started"}
    if len(started) > 120 or len(started) != sum(
        row["event"] == "started" for row in attempts
    ):
        raise ValueError("Invalid or duplicate P6 start markers")
    for case in cases:
        for variant in STRATEGIES:
            key = f"{case.key}/{variant}"
            if key in started:
                continue
            if (
                variant != "agent"
                and sum(not k.endswith("/agent") for k in started) >= MAX_QA_ATTEMPTS
            ):
                raise ValueError("P6 QA attempt budget exhausted")
            request = {
                **case.request(),
                "strategy": "hybrid_rerank" if variant == "agent" else variant,
            }
            if case.dataset == "swin":
                request["family"] = "swin_v1"
            _append(journal_path, {"event": "started", "key": key, "request": request})
            started.add(key)
            started_at = perf_counter()
            record: dict = {"event": "completed", "key": key, "variant": variant}
            try:
                if variant == "agent":
                    answer = await agent.run(AgentRequest.model_validate(request))
                    record["answer"] = answer.model_dump(mode="json")
                else:
                    search_request = SearchRequest.model_validate(request)
                    search = await asyncio.to_thread(service.search, search_request)
                    record["retrieval"] = search.model_dump(mode="json")
                    qa = QAService(ROOT, FixedSearch(search_request, search))
                    answer = await qa.answer(QARequest.model_validate(request))
                    record["answer"] = answer.model_dump(mode="json")
            except Exception as exc:  # noqa: BLE001 - preserve a terminal record for every frozen attempt
                record["event"] = "error"
                record["error_type"] = type(exc).__name__
            record["elapsed_seconds"] = perf_counter() - started_at
            _append(journal_path, record)
            print(f"{record['event']} {key}", flush=True)
    print("P6 run ended; use report to score and seal unchanged outputs")


def _registry() -> dict[str, dict]:
    paths = [
        ROOT / "data/processed/swin/chunks/v2/chunks.jsonl",
        ROOT / "data/processed/qasper_external/chunks/v2/chunks.jsonl",
    ]
    return {row["chunk_id"]: row for path in paths for row in read_jsonl(path)}


def report() -> dict:
    manifest = _manifest()
    cases, gold = _cases(include_gold=True)
    attempts = read_jsonl(RUN_DIR / "attempts.jsonl")
    starts = [r for r in attempts if r["event"] == "started"]
    terminals = [r for r in attempts if r["event"] in {"completed", "error"}]
    expected = {f"{case.key}/{variant}" for case in cases for variant in STRATEGIES}
    if {r["key"] for r in starts} != expected or len(starts) != 120:
        raise ValueError("P6 attempts incomplete; no replacement results allowed")
    if len({r["key"] for r in terminals}) != len(terminals):
        raise ValueError("Duplicate P6 terminal records")
    if not {r["key"] for r in terminals}.issubset(expected):
        raise ValueError("Unknown P6 terminal record")
    saved = {r["key"]: r for r in terminals}
    # An interrupted attempt consumes its started slot and is never retried.
    for key in expected - saved.keys():
        saved[key] = {
            "event": "error",
            "key": key,
            "error_type": "InterruptedAfterStart",
            "elapsed_seconds": None,
        }
    index_fingerprint = manifest["identity"]["index_fingerprint"]
    registry = _registry()
    corpus = {
        row["unit_id"]: row["text"]
        for row in read_jsonl(
            ROOT / "data/processed/qasper_external/v1/validation_corpus.jsonl"
        )
    }
    specs = {
        item["id"]: item
        for item in json.loads(
            (ROOT / "data/eval/swin_evidence.json").read_text(encoding="utf-8")
        )["evidence"]
    }
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    details = []
    predictions: dict[str, dict] = {variant: {} for variant in STRATEGIES}
    for case in cases:
        for variant in STRATEGIES:
            key = f"{case.key}/{variant}"
            row = saved[key]
            detail = {
                "key": key,
                "dataset": case.dataset,
                "variant": variant,
                "event": row["event"],
                "elapsed_seconds": row["elapsed_seconds"],
            }
            if row["event"] == "error":
                detail["error_type"] = row["error_type"]
                grouped[(case.dataset, variant)].append(detail)
                details.append(detail)
                continue
            answer = (
                AgentResponse.model_validate(row["answer"])
                if variant == "agent"
                else QAResponse.model_validate(row["answer"])
            )
            if variant == "agent":
                cited = (
                    [citation.evidence for citation in answer.answer.citations]
                    if answer.answer
                    else []
                )
                text = answer.answer.answer if answer.answer else ""
                status = answer.status
                paid_calls = answer.usage.paid_calls
                prompt_tokens = answer.usage.prompt_tokens
                completion_tokens = answer.usage.completion_tokens
                retrieval = None
                model_invalid_citations = (
                    answer.answer.invalid_citation_ids if answer.answer else []
                )
            else:
                search = SearchResponse.model_validate(row["retrieval"])
                if search.index_fingerprint != index_fingerprint:
                    raise ValueError("P6 retrieval fingerprint changed")
                retrieval = search.results
                cited = [citation.evidence for citation in answer.citations]
                text = answer.answer
                status = answer.status
                paid_calls = answer.usage.generation_calls
                prompt_tokens = answer.usage.prompt_tokens
                completion_tokens = answer.usage.completion_tokens
                model_invalid_citations = answer.invalid_citation_ids
            invalid_citations = [
                c.chunk_id
                for c in cited
                if c.chunk_id not in registry
                or (
                    case.dataset == "qasper"
                    and not c.source.source_path.startswith(
                        case.filters["path_prefixes"][0]
                    )
                )
            ]
            detail.update(
                {
                    "status": status,
                    "answer": text,
                    "citation_count": len(cited),
                    "citation_ids": [c.chunk_id for c in cited],
                    "invalid_citation_ids": list(
                        dict.fromkeys([*model_invalid_citations, *invalid_citations])
                    ),
                    "paid_calls": paid_calls,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "abstained": status == "insufficient_evidence"
                    or INSUFFICIENT in text,
                }
            )
            if retrieval is not None:
                chunks = [registry[item.chunk_id] for item in retrieval]
                detail["retrieval"] = (
                    score_swin(gold[case.key]["required_evidence"], specs, chunks)
                    if case.dataset == "swin"
                    else score_qasper_retrieval(gold[case.key], chunks, corpus)
                )
            cited_chunks = [
                registry[item.chunk_id]
                for item in cited
                if item.chunk_id not in invalid_citations
            ]
            detail["citation_evidence"] = (
                score_swin(gold[case.key]["required_evidence"], specs, cited_chunks)
                if case.dataset == "swin"
                else score_qasper_retrieval(gold[case.key], cited_chunks, corpus)
            )
            if case.dataset == "qasper":
                _, complete = unit_coverage(cited_chunks, corpus)
                predictions[variant][case.id] = {
                    "answer": answer_for_official_score(text, detail["abstained"]),
                    "evidence": [corpus[unit] for unit in sorted(complete)],
                }
            detail["gold_answer_status"] = (
                gold[case.key].get("answer_status") if case.dataset == "swin" else None
            )
            grouped[(case.dataset, variant)].append(detail)
            details.append(detail)
    summaries = []
    for (dataset, variant), rows in grouped.items():
        recorded = [row for row in rows if row["event"] == "completed"]
        answered = [
            row
            for row in recorded
            if row["status"]
            in {"answered", "completed", "insufficient_evidence", "review_required"}
        ]
        scored = [row["retrieval"] for row in recorded if "retrieval" in row]
        citation_metric = (
            "locator_recall" if dataset == "swin" else "complete_unit_recall"
        )
        citation_scores = [
            row["citation_evidence"][citation_metric]
            for row in recorded
            if row["citation_evidence"][citation_metric] is not None
        ]
        entry = {
            "dataset": dataset,
            "variant": variant,
            "expected_n": 8 if dataset == "swin" else 32,
            "recorded_n": len(recorded),
            "answered_n": len(answered),
            "failed_n": len(rows) - len(answered),
            "status_counts": dict(Counter(row["status"] for row in recorded)),
            "citation_present_n": sum(row["citation_count"] > 0 for row in recorded),
            "invalid_citation_n": sum(
                len(row["invalid_citation_ids"]) for row in recorded
            ),
            "citation_evidence_metric": citation_metric,
            "citation_evidence_recall": mean(citation_scores)
            if citation_scores
            else None,
            "citation_evidence_denominator": len(citation_scores),
            "abstained_n": sum(row["abstained"] for row in recorded),
            "paid_calls_reported": sum(row["paid_calls"] for row in recorded),
            "prompt_tokens_reported": sum(row["prompt_tokens"] for row in recorded),
            "completion_tokens_reported": sum(
                row["completion_tokens"] for row in recorded
            ),
            "elapsed_seconds_median": median(
                row["elapsed_seconds"]
                for row in rows
                if row["elapsed_seconds"] is not None
            )
            if any(row["elapsed_seconds"] is not None for row in rows)
            else None,
        }
        if scored:
            metric = "locator_recall" if dataset == "swin" else "complete_unit_recall"
            entry["retrieval_metric"] = metric
            valid = [r[metric] for r in scored if r[metric] is not None]
            entry["retrieval_at_8"] = mean(valid) if valid else None
            entry["retrieval_denominator"] = sum(r[metric] is not None for r in scored)
        if dataset == "qasper":
            refs = {
                case.id: qasper_references(gold[case.key])
                for case in cases
                if case.dataset == "qasper"
            }
            entry["qasper_official"] = evaluate(refs, predictions[variant])
            negatives = [
                row
                for row in recorded
                if all(
                    reference["type"] == "none"
                    for reference in refs[row["key"].split("/")[2]]
                )
            ]
            entry["unanswerable_n"] = len(negatives)
            entry["unanswerable_recognized_n"] = sum(
                row["abstained"] for row in negatives
            )
        else:
            negative = [
                row
                for row in recorded
                if row["gold_answer_status"] in {"insufficient", "conflicting"}
            ]
            entry["swin_negative_status_n"] = len(negative)
            entry["swin_negative_recognized_n"] = sum(
                row["abstained"] for row in negative
            )
        summaries.append(entry)
    output = {
        "version": "p6-frozen-report-v1",
        "manifest_sha256": digest(RUN_DIR / "manifest.json"),
        "attempts_sha256": digest(RUN_DIR / "attempts.jsonl"),
        "agent_paid_journal_sha256": digest(RUN_DIR / "agent-paid-journal.jsonl")
        if (RUN_DIR / "agent-paid-journal.jsonl").exists()
        else None,
        "summary": summaries,
        "details": details,
        "semantic_audit": "not_human_reviewed",
        "cost_usd_actual": None,
    }
    report_path = RUN_DIR / "report.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != output:
            raise ValueError("P6 report is already sealed with different content")
    else:
        _write_json(report_path, output)
    print(
        json.dumps(
            {"summary": summaries, "report_sha256": digest(report_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "run", "report"])
    args = parser.parse_args()
    with FileLock(RUN_DIR.parent / ".p6-v1.lock", timeout=0):
        if args.command == "freeze":
            freeze()
        elif args.command == "run":
            asyncio.run(execute())
        else:
            report()


if __name__ == "__main__":
    main()
