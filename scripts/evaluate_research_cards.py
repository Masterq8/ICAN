"""Freeze, run once, and score the P4.6 eight-paper quality acceptance set."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.api.app import load_config
from ican.evaluation.data import digest
from ican.evaluation.research_card import (
    collect_prior_source_ids,
    evidence_identity,
    score_quality_review,
)
from ican.research.auto_schema import AutoCardRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.field_rules import diagnose_field_assignment
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.research.submission import diagnose_card_submission
from ican.retrieval.hybrid import HybridEvidenceSearchService

CONFIG_PATH = ROOT / "configs/evaluation/p46-quality-v1.json"
RUN_DIR = ROOT / "data/processed/evaluation/p46-quality-v1"
DOC_DIR = ROOT / "docs/evaluation/p46-quality-v1"
FULL_MANIFEST = RUN_DIR / "manifest.json"
PUBLIC_MANIFEST = DOC_DIR / "manifest.json"
REVIEW_PATH = DOC_DIR / "manual-review.json"
REPORT_PATH = DOC_DIR / "report.md"
METRICS_PATH = DOC_DIR / "metrics.json"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def request_for(case, collection):
    return AutoCardRequest(
        query=case["query"], collection=collection, source_id=case["source_id"]
    )


def services(*, paid=False):
    index_config = load_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, index_config)
    research = ResearchService(
        ROOT,
        index_config,
        evidence,
        store=ResearchStore(RUN_DIR / "records"),
    )
    kwargs = {
        "journal": PaidJournal(RUN_DIR / "paid-journal.jsonl", 8),
        "trace_directory": RUN_DIR / "traces",
    }
    if not paid:
        kwargs.pop("journal")
    return ResearchAutoService(ROOT, index_config, evidence, research, **kwargs)


def source_hashes():
    paths = [
        CONFIG_PATH,
        ROOT / "configs/agent/v2.json",
        ROOT / "ican/research/auto_schema.py",
        ROOT / "ican/research/auto_service.py",
        ROOT / "ican/research/field_rules.py",
        ROOT / "ican/research/submission.py",
        ROOT / "ican/evaluation/research_card.py",
        ROOT / "scripts/evaluate_research_cards.py",
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def prepare():
    config = read_json(CONFIG_PATH)
    cases = config["cases"]
    if len(cases) != 8 or len({case["source_id"] for case in cases}) != 8:
        raise ValueError("Quality set must contain eight distinct papers")
    prior = collect_prior_source_ids(
        [
            ROOT / "data/processed/evaluation",
            ROOT / "data/processed/research",
        ]
    )
    current = {case["source_id"] for case in cases}
    overlap = current & (prior - collect_prior_source_ids([RUN_DIR]))
    if overlap:
        raise ValueError(f"Quality cases were used by prior runs: {sorted(overlap)}")
    if FULL_MANIFEST.exists() or PUBLIC_MANIFEST.exists():
        raise ValueError("Quality manifest already exists")

    auto = services()
    full_cases = {}
    public_cases = {}
    for case in cases:
        request = request_for(case, config["collection"])
        candidate, index_fingerprint = auto._paper_evidence(request)
        if candidate.title != case["title"]:
            raise ValueError(f"{case['key']}: configured title does not match corpus")
        if len(candidate.evidence) != 6:
            raise ValueError(f"{case['key']}: expected six frozen evidence items")
        identities = [evidence_identity(item) for item in candidate.evidence]
        full_cases[case["key"]] = {
            "request": request.model_dump(mode="json"),
            "title": candidate.title,
            "source_path": candidate.source_path,
            "source_version": candidate.source_version,
            "index_fingerprint": index_fingerprint,
            "evidence": [item.model_dump(mode="json") for item in candidate.evidence],
        }
        public_cases[case["key"]] = {
            "request": request.model_dump(mode="json"),
            "title": candidate.title,
            "source_path": candidate.source_path,
            "source_version": candidate.source_version,
            "index_fingerprint": index_fingerprint,
            "evidence": identities,
        }
    identity = {
        "version": config["version"],
        "model": config["model"],
        "max_paid_calls": config["max_paid_calls"],
        "source_sha256": source_hashes(),
    }
    write_json(FULL_MANIFEST, {**identity, "cases": full_cases}, exclusive=True)
    write_json(
        PUBLIC_MANIFEST,
        {
            **identity,
            "cases": public_cases,
            "full_manifest_sha256": digest(FULL_MANIFEST),
            "contains_source_text": False,
        },
        exclusive=True,
    )
    print(json.dumps({"prepared": len(cases), "manifest": str(PUBLIC_MANIFEST)}))


def verify_identity(manifest):
    for relative, expected in manifest["source_sha256"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Run source changed after prepare: {relative}")
    if read_json(PUBLIC_MANIFEST)["full_manifest_sha256"] != digest(FULL_MANIFEST):
        raise ValueError("Full and public manifests do not match")


def matching_frozen_evidence(auto, case):
    request = AutoCardRequest.model_validate(case["request"])
    candidate, fingerprint = auto._paper_evidence(request)
    actual = [evidence_identity(item) for item in candidate.evidence]
    expected = [
        {
            "chunk_id": item["chunk_id"],
            "source_id": item["source"]["source_id"],
            "source_path": item["source"]["source_path"],
            "source_version": item["source"]["source_version"],
            "location": item["source"]["location"],
            "text_sha256": digest_text(item["text"]),
        }
        for item in case["evidence"]
    ]
    if actual != expected or fingerprint != case["index_fingerprint"]:
        raise ValueError("Frozen evidence or index identity changed")
    return request


def digest_text(text):
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_trace(before):
    after = set((RUN_DIR / "traces").glob("*.json"))
    created = after - before
    if len(created) != 1:
        raise ValueError(f"Expected one new trace, found {len(created)}")
    return created.pop()


async def run_cases():
    manifest = read_json(FULL_MANIFEST)
    verify_identity(manifest)
    auto = services(paid=True)
    for key, case in manifest["cases"].items():
        started = RUN_DIR / f"{key}.started.json"
        result_path = RUN_DIR / f"{key}.result.json"
        if result_path.exists():
            continue
        if started.exists():
            print(json.dumps({"case": key, "status": "started_without_retry"}))
            continue
        request = matching_frozen_evidence(auto, case)
        write_json(
            started,
            {
                "request": request.model_dump(mode="json"),
                "manifest_sha256": digest(FULL_MANIFEST),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            exclusive=True,
        )
        before = set((RUN_DIR / "traces").glob("*.json"))
        try:
            card = await auto.auto_card(request)
            trace = new_trace(before)
            trace_data = read_json(trace)
            output = {
                "status": "completed",
                "tool_diagnosis": trace_data["submission_diagnostic"],
                "trace": trace.name,
                "trace_sha256": digest(trace),
                "usage": card.usage.model_dump(mode="json"),
                "card": card.model_dump(mode="json"),
            }
        except Exception as error:  # noqa: BLE001 -- retain each paid-call failure and continue fresh cases
            created = set((RUN_DIR / "traces").glob("*.json")) - before
            trace = created.pop() if len(created) == 1 else None
            trace_data = read_json(trace) if trace else {}
            output = {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error)[:500],
                "tool_diagnosis": trace_data.get(
                    "submission_diagnostic",
                    {
                        "status": "rejected",
                        "code": "missing_trace",
                        "issues": [],
                    },
                ),
                "trace": trace.name if trace else None,
                "trace_sha256": digest(trace) if trace else None,
            }
        write_json(result_path, output, exclusive=True)
        print(
            json.dumps(
                {
                    "case": key,
                    "status": output["status"],
                    "diagnostic": output["tool_diagnosis"]["code"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def case_outputs(manifest):
    outputs = {}
    for key, case in manifest["cases"].items():
        result = read_json(RUN_DIR / f"{key}.result.json")
        trace = read_json(RUN_DIR / "traces" / result["trace"])
        diagnosis = diagnose_card_submission(
            trace.get("model_action"),
            {item["chunk_id"] for item in case["evidence"]},
        )
        fields = (
            [field.name for field in diagnosis.draft.fields] if diagnosis.draft else []
        )
        outputs[key] = {
            "tool_success": diagnosis.status == "accepted",
            "diagnosis": diagnosis.model_dump(mode="json", exclude={"draft"}),
            "submitted_fields": fields,
            "run_status": result["status"],
            "semantic_diagnostics": {
                field.name: [
                    item.model_dump(mode="json")
                    for item in diagnose_field_assignment(
                        field.name, field.value, field.quote
                    )
                ]
                for field in diagnosis.draft.fields
            }
            if diagnosis.draft
            else {},
        }
    return outputs


def format_rate(item):
    rate = "n/a" if item["rate"] is None else f"{item['rate'] * 100:.1f}%"
    return f"{rate}（{item['numerator']}/{item['denominator']}）"


def finalize():
    manifest = read_json(FULL_MANIFEST)
    verify_identity(manifest)
    review = read_json(REVIEW_PATH)
    outputs = case_outputs(manifest)
    metrics = score_quality_review(outputs, review, total_cases=len(outputs))
    write_json(METRICS_PATH, {"metrics": metrics, "cases": outputs})

    lines = [
        "# P4.6 新论文定向质量验收",
        "",
        "## 结论指标",
        "",
        f"- 工具提交成功率：{format_rate(metrics['tool_submission_success'])}",
        f"- 原文支持率：{format_rate(metrics['evidence_support_rate'])}",
        f"- 字段归类正确率：{format_rate(metrics['field_classification_accuracy'])}",
        f"- 缺失字段识别率：{format_rate(metrics['missing_field_identification_rate'])}",
        f"- 已有字段召回率：{format_rate(metrics['present_field_recall'])}",
        "",
        "字段指标只统计协议提交成功的样本；失败样本仍进入工具成功率分母。",
        "",
        "## 逐篇诊断",
        "",
        "| 样本 | 工具诊断 | 运行状态 | 提交字段 | 遗漏的已有字段 | 规则提示 |",
        "|---|---|---|---|---|---|",
    ]
    for key, output in outputs.items():
        item = review["cases"][key]
        rule_codes = [
            diagnostic["code"]
            for diagnostics in output["semantic_diagnostics"].values()
            for diagnostic in diagnostics
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    key,
                    output["diagnosis"]["code"],
                    output["run_status"],
                    ", ".join(output["submitted_fields"]) or "—",
                    ", ".join(item["omitted_present_fields"]) or "—",
                    ", ".join(rule_codes) or "—",
                ]
            )
            + " |"
        )
    lines.extend(["", "## 工具错误细节", ""])
    failures = 0
    for key, output in outputs.items():
        if output["diagnosis"]["code"] == "accepted":
            continue
        failures += 1
        lines.append(f"### {key}: `{output['diagnosis']['code']}`")
        lines.append("")
        for issue in output["diagnosis"]["issues"]:
            path = ".".join(str(part) for part in issue["path"]) or "action"
            lines.append(f"- `{path}`：{issue['message']}")
        lines.append("")
    if failures == 0:
        lines.append("8 个样本均完成协议提交；语义问题见逐篇诊断和人工审核。")
        lines.append("")
    lines.extend(
        [
            "## 字段混淆",
            "",
            *(
                [f"- `{key}`：{value}" for key, value in metrics["confusions"].items()]
                or ["- 未发现字段类型混淆。"]
            ),
            "",
            "## 审核边界",
            "",
            "人工审核只使用模型实际收到的六条证据。未在这六条证据出现的全文信息不计为可提取字段；规则诊断不自动改写模型输出。",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "run", "finalize"])
    args = parser.parse_args()
    lock = ROOT / "data/processed/.p46-quality.lock"
    with FileLock(lock, timeout=0):
        if args.command == "prepare":
            prepare()
        elif args.command == "run":
            asyncio.run(run_cases())
        else:
            finalize()


if __name__ == "__main__":
    main()
