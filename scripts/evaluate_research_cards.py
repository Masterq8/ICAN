"""Freeze, run once, and score the P4.6 eight-paper quality acceptance set."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.agent.journal import PaidJournal
from ican.api.app import load_config
from ican.evaluation.data import digest
from ican.evaluation.research_audit import verify_audit_inputs
from ican.evaluation.research_card import (
    collect_prior_source_ids,
    evidence_identity,
    raw_card_fields,
    score_quality_review,
    score_raw_draft_review,
    validate_review_binding,
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
    overlap = current & prior
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


def verify_identity(manifest, *, check_sources=True):
    if check_sources:
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
        if not result.get("trace"):
            raise ValueError(f"{key}: no trace; audit is incomplete")
        if Path(result["trace"]).name != result["trace"]:
            raise ValueError("Trace name must be a basename")
        if digest(RUN_DIR / "traces" / result["trace"]) != result["trace_sha256"]:
            raise ValueError(f"{key}: trace hash changed")
        trace = read_json(RUN_DIR / "traces" / result["trace"])
        if trace["request"] != case["request"] or sorted(
            trace["selected_evidence_ids"]
        ) != sorted(item["chunk_id"] for item in case["evidence"]):
            raise ValueError(f"{key}: trace does not match frozen request/evidence")
        diagnosis = diagnose_card_submission(
            trace.get("model_action"),
            {item["chunk_id"] for item in case["evidence"]},
        )
        raw_fields = raw_card_fields(trace.get("model_action"))
        if diagnosis.code != result["tool_diagnosis"]["code"]:
            raise ValueError(f"{key}: reanalysis differs from recorded tool diagnosis")
        fields = (
            [field.name for field in diagnosis.draft.fields] if diagnosis.draft else []
        )
        outputs[key] = {
            "tool_success": diagnosis.status == "accepted",
            "diagnosis": diagnosis.model_dump(mode="json", exclude={"draft"}),
            "submitted_fields": fields,
            "raw_submitted_fields": [field["name"] for field in raw_fields],
            "raw_fields": raw_fields,
            "run_status": result["status"],
            "semantic_diagnostics": [
                {
                    "occurrence": index,
                    "name": field["name"],
                    "diagnostics": [
                        item.model_dump(mode="json")
                        for item in diagnose_field_assignment(
                            field["name"], field["value"], field["quote"]
                        )
                    ],
                }
                for index, field in enumerate(raw_fields, start=1)
            ],
            "accepted_semantic_diagnostics": {
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
    verify_identity(manifest, check_sources=False)
    usage = verify_audit_inputs(
        ROOT, RUN_DIR, manifest, read_json(DOC_DIR / "run-seal.json")
    )
    review = read_json(REVIEW_PATH)
    provenance = review.get("review_provenance")
    if provenance and (
        provenance.get("artifact") != "pro-review.json"
        or digest(DOC_DIR / "pro-review.json") != provenance.get("sha256")
    ):
        raise ValueError("AI review provenance artifact identity differs")
    outputs = case_outputs(manifest)
    validate_review_binding(
        {key: value["raw_fields"] for key, value in outputs.items()}, review
    )
    for key, item in review["cases"].items():
        evidence_ids = {e["chunk_id"] for e in manifest["cases"][key]["evidence"]}
        anchors = item.get("presence_evidence_ids", {})
        if (
            set(anchors) != set(item["expected_present_fields"])
            or not set(anchors.values()) <= evidence_ids
        ):
            raise ValueError(f"{key}: missing/invalid presence evidence anchors")
    accepted_metrics = score_quality_review(outputs, review, total_cases=len(outputs))
    raw_metrics = score_raw_draft_review(review, total_cases=len(outputs))
    metrics = {
        "tool_submission_success": accepted_metrics["tool_submission_success"],
        "evidence_support_rate": raw_metrics["evidence_support_rate"],
        "field_classification_accuracy": raw_metrics["field_classification_accuracy"],
        "missing_field_identification_rate": raw_metrics[
            "missing_field_identification_rate"
        ],
        "present_field_recall": raw_metrics["present_field_recall"],
        "confusions": raw_metrics["confusions"],
        "field_metric_scope": raw_metrics["scope"],
    }
    write_json(
        METRICS_PATH,
        {
            "predeclared_metrics": accepted_metrics,
            "supplementary_raw_draft_metrics": metrics,
            "reviewer_type": review["reviewer_type"],
            "human_review_status": review["human_review_status"],
            "ai_review_status": review.get("ai_review_status", "initial"),
            "review_provenance": review.get("review_provenance"),
            "usage": usage,
            "audit_inputs": {
                "review_sha256": digest(REVIEW_PATH),
                "run_seal_sha256": digest(DOC_DIR / "run-seal.json"),
                "scorer_sha256": digest(ROOT / "ican/evaluation/research_card.py"),
            },
            "cases": outputs,
        },
    )

    accepted_count = accepted_metrics["tool_submission_success"]["numerator"]
    review_status = review["human_review_status"]
    review_notice = (
        "语义审核已由人类完成，以下指标依照已记录的审核判断计算。"
        if review["reviewer_type"] == "human" and review_status == "completed"
        else "语义审核尚未经人类确认。以下支持率、归类率和缺失率均为暂定值。"
    )
    lines = [
        "# P4.6 新论文定向质量验收",
        "",
        f"本轮质量检查已执行：{len(outputs)} 篇新论文成功提交 {accepted_count} 篇。具体失败原因见逐篇诊断；本报告不自动判定产品验收通过。",
        "",
        f"**{review_notice}**",
        f"AI 复核状态：{review.get('ai_review_status', 'initial')}；审核身份：{review['reviewer_type']}。",
        "",
        "## 预先约定口径：成功提交样本",
        "",
        f"- 工具提交成功率：{format_rate(accepted_metrics['tool_submission_success'])}",
        f"- 原文支持率：{format_rate(accepted_metrics['evidence_support_rate'])}",
        f"- 字段归类正确率：{format_rate(accepted_metrics['field_classification_accuracy'])}",
        f"- 缺失字段识别率：{format_rate(accepted_metrics['missing_field_identification_rate'])}",
        f"- 已有字段槽位覆盖率：{format_rate(accepted_metrics['present_field_recall'])}",
        "",
        f"字段分母仅来自 {accepted_count} 篇成功卡片；不可把该口径解读为整体可靠。",
        "",
        "## 补充口径：全部可解析原始草稿（事后增加）",
        "",
        f"- 工具提交成功率：{format_rate(metrics['tool_submission_success'])}",
        f"- 原文支持率：{format_rate(metrics['evidence_support_rate'])}",
        f"- 字段归类正确率：{format_rate(metrics['field_classification_accuracy'])}",
        f"- 缺失字段识别率：{format_rate(metrics['missing_field_identification_rate'])}",
        f"- 已有字段槽位覆盖率：{format_rate(metrics['present_field_recall'])}",
        "",
        "字段指标统计全部可解析原始草稿中的字段，包括因重复字段而被 schema 拒绝的草稿；规则未改写原始输出。",
        "槽位覆盖只表示字段名出现，不要求该字段内容支持且正确；它不是正确内容召回率。",
        "",
        f"用量：{usage['paid_calls']} 次 deepseek-flash；{usage['prompt_tokens']} 输入 token、{usage['completion_tokens']} 输出 token。供应商未返回实际费用。",
        "",
        "## 逐篇诊断",
        "",
        "| 样本 | 工具诊断 | 运行状态 | 提交字段 | 遗漏的已有字段 | 规则提示 |",
        "|---|---|---|---|---|---|",
    ]
    provenance = review.get("review_provenance")
    if provenance:
        lines[6:6] = [
            "",
            "复核过程与分歧裁定见 [AI复核记录](review-adjudication.md)。",
            (
                f"额外语义审核：{provenance['review_paid_calls']} 次 {provenance['review_model']}，"
                "与下文原始生成用量分开计算，未重新生成卡片。"
            ),
        ]
    for key, output in outputs.items():
        item = review["cases"][key]
        rule_codes = [
            diagnostic["code"]
            for field in output["semantic_diagnostics"]
            for diagnostic in field["diagnostics"]
        ]
        counts = Counter(output["raw_submitted_fields"])
        submitted = ", ".join(
            f"{name}×{count}" if count > 1 else name for name, count in counts.items()
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    key,
                    output["diagnosis"]["code"],
                    output["run_status"],
                    submitted or "—",
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
        raw_counts = Counter(output["raw_submitted_fields"])
        repeated = {name: count for name, count in raw_counts.items() if count > 1}
        if repeated:
            lines.append(
                "- 重复字段："
                + "、".join(f"`{name}` × {count}" for name, count in repeated.items())
            )
        unsupported = [
            f"#{index + 1} `{field['name']}`"
            for index, field in enumerate(review["cases"][key]["fields"])
            if not field["evidence_supported"]
        ]
        if unsupported:
            lines.append("- 原文不支持：" + "、".join(unsupported))
        misclassified = [
            f"#{index + 1} `{field['name']}` → `{field['correct_type']}`"
            for index, field in enumerate(review["cases"][key]["fields"])
            if not field["type_correct"]
        ]
        if misclassified:
            lines.append("- 字段错分：" + "、".join(misclassified))
        lines.append("")
    if failures == 0:
        lines.append(
            f"{len(outputs)} 个样本均完成协议提交；语义问题见逐篇诊断和人工审核。"
        )
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
            "审核使用模型实际收到的六条证据（每条最多 2200 字符）；本轮最大 2156 字符，无实际截断。原文支持要求引用为连续原文且语义支持字段值，大小写调整、移除文献标记等忠实归一化不等于伪造引用。",
            "",
            "字段缺失只表示输入证据未出现，不等于全文未报告。九类字段仅可各出现一次的现有协议与多数据集、多结果输出冲突，是本轮主要阻断因素。下一步应在新协议设计中表示同类多个条目，并以离线原始输出回放测试验证；本轮结果不重跑或改记成功。",
            "",
            f"确定性规则只覆盖强词法冲突，未触发规则不证明字段正确。当前审核发现 {sum(metrics['confusions'].values())} 处类型混淆，具体类别见上表；规则仅覆盖 dataset/metric/result。",
            "",
            "源代码身份固定在 2937a56；run-seal.json 为运行完成后的首次归档封存。finalize 检查结果、trace、journal、源码快照和审核字段哈希，不产生模型调用。",
            "",
            f"人工复核：打开 manual-review.json，按 occurrence 对照 metrics.json 中 raw_fields 以及 human-review.md 的证据；保留绑定哈希，修改判断与理由后执行 finalize 重算。当前 human_review_status={review_status}。",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    packet = [
        "# P4.6 人工复核工作表",
        "",
        f"当前 reviewer_type={review['reviewer_type']}，ai_review_status={review.get('ai_review_status', 'initial')}，human_review_status={review_status}。请核对字段类型、引文支持与遗漏；审核单位为下方 occurrence（从 0 开始），不是去重后的字段名。",
        "修改 manual-review.json 中的判断、理由和字段存在性；保留原始字段哈希。人工完成后填写本人 reviewer、reviewer_type=human 和 human_review_status=completed，再运行 finalize。",
        "",
    ]
    for key, case in manifest["cases"].items():
        label = review["cases"][key]
        packet += [
            f"## {key} — {case['title']}",
            "",
            f"来源：{case['request']['source_id']}；版本：{case['source_version']}",
            "",
            "证据中应有字段：" + ", ".join(label["expected_present_fields"]),
            "当前遗漏：" + (", ".join(label["omitted_present_fields"]) or "无"),
            "",
        ]
        if label.get("presence_review"):
            packet += ["### 字段存在性复核", ""]
            for name, verdict in label["presence_review"].items():
                packet += [
                    f"- **{name}：存在**。{verdict['reason']}",
                    f"  原文：{verdict['excerpt']}",
                    f"  来源：`{verdict['evidence_id']}`",
                ]
            for name, reason in label.get("absence_review", {}).items():
                packet.append(f"- **{name}：当前证据未提供**。{reason}")
            packet.append("")
        for index, (raw, audit) in enumerate(
            zip(outputs[key]["raw_fields"], label["fields"], strict=True)
        ):
            packet += [
                f"### 字段 {index}: {raw['name']}",
                "",
                f"值：{raw['value']}",
                "",
                f"引用：{raw['quote']}",
                "",
                f"证据 ID：`{raw['evidence_id']}`",
                f"当前审核：原文支持={audit['evidence_supported']}；归类正确={audit['type_correct']}；建议类型={audit['correct_type']}",
                audit["note"],
                "",
            ]
            if audit.get("ambiguity"):
                packet += [
                    "分类歧义：" + audit["ambiguity"]["resolution"],
                    "",
                ]
        packet += ["### 实际输入证据", ""]
        for evidence in case["evidence"]:
            packet += [
                f"#### {evidence['chunk_id']}",
                "",
                json.dumps(evidence["source"]["location"], ensure_ascii=False),
                "",
                evidence["text"][:2200],
                "",
            ]
    (DOC_DIR / "human-review.md").write_text(
        "\n".join(line.rstrip() for line in "\n".join(packet).split("\n")),
        encoding="utf-8",
        newline="\n",
    )
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
