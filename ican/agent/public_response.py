from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .schema import (
    AgentResponse,
    PublicAgentArtifact,
    PublicAgentEvent,
    PublicAgentResponse,
    PublicClaimText,
    PublicClaimVerdict,
    PublicEvidenceResult,
)

PUBLIC_TOOL_NAMES = {
    "search_evidence",
    "read_evidence",
    "trace_config",
    "calculate",
    "verify_claims",
    "record_screening",
    "record_extraction",
    "build_research_report",
    "submit_claims",
    "gen_answer",
    "complete",
}
_SAFE_STRATEGIES = {"dense", "dense_scoped", "bm25", "hybrid", "hybrid_rerank"}
_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"
)


def _bounded_text(value: Any, limit: int = 100) -> str:
    if not isinstance(value, str):
        return ""
    clean = " ".join(value.split())
    clean = _SECRET_PATTERN.sub(r"\1=[已隐藏]", clean)
    if len(clean) > limit:
        return clean[: limit - 1].rstrip() + "…"
    return clean


def _argument_summary(tool: str, arguments: Any) -> str:
    if not isinstance(arguments, dict):
        return "参数已按安全规则省略"

    if tool == "search_evidence":
        query = _bounded_text(arguments.get("query"), 96)
        sources = arguments.get("source_types")
        safe_sources = [
            item
            for item in sources
            if item in {"paper", "code", "config", "documentation"}
        ] if isinstance(sources, list) else []
        strategy = arguments.get("strategy")
        strategy_text = strategy if strategy in _SAFE_STRATEGIES else "当前检索策略"
        scope_text = f"；来源范围：{', '.join(safe_sources)}" if safe_sources else ""
        query_text = f"“{query}”" if query else "当前研究问题"
        return _bounded_text(f"查询 {query_text}{scope_text}；策略：{strategy_text}", 240)

    if tool == "read_evidence":
        structure = _bounded_text(arguments.get("structure"), 90)
        path = _bounded_text(arguments.get("source_path"), 90)
        details = " · ".join(value for value in (structure, path) if value)
        return _bounded_text(f"读取指定证据片段{f'：{details}' if details else ''}", 240)

    if tool == "trace_config":
        field = _bounded_text(arguments.get("field"), 80)
        path = _bounded_text(arguments.get("config_path"), 90)
        details = " · ".join(value for value in (field, path) if value)
        return _bounded_text(f"追踪配置字段{f'：{details}' if details else ''}", 240)

    if tool == "calculate":
        expression = _bounded_text(arguments.get("expression"), 96)
        count = len(arguments.get("evidence_ids", [])) if isinstance(arguments.get("evidence_ids"), list) else 0
        support = f"；关联 {count} 项证据" if count else ""
        return _bounded_text(f"计算 {expression or '给定数值'}{support}", 240)

    if tool in {"verify_claims", "submit_claims"}:
        claims = arguments.get("claims")
        evidence = arguments.get("evidence_ids")
        claim_count = len(claims) if isinstance(claims, list) else 0
        evidence_count = len(evidence) if isinstance(evidence, list) else 0
        return f"提交 {claim_count} 条结论、{evidence_count} 项证据进行核查"

    if tool == "record_screening":
        decision = arguments.get("decision")
        decision = decision if decision in {"include", "exclude", "hold"} else "待核查"
        return f"保存筛选结论：{decision}"

    if tool == "record_extraction":
        fields = arguments.get("fields")
        count = len(fields) if isinstance(fields, list) else 0
        return f"保存 {count} 个结构化字段"

    if tool == "build_research_report":
        records = arguments.get("record_ids")
        count = len(records) if isinstance(records, list) else 0
        return f"基于 {count} 条研究记录生成报告"

    if tool == "gen_answer":
        evidence = arguments.get("evidence_ids")
        count = len(evidence) if isinstance(evidence, list) else 0
        return f"基于 {count} 项保留证据生成回答"

    if tool == "complete":
        return "提交任务结束状态"

    return "参数已按安全规则省略"


def _parse_result(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _result_summary(tool: str, raw: Any) -> tuple[str, bool]:
    result = _parse_result(raw)
    if result is None:
        return "工具已返回结果", False
    if "error" in result:
        return "工具未能完成", True

    evidence = result.get("evidence")
    if isinstance(evidence, list):
        count = len(evidence)
        if tool == "search_evidence":
            return f"检索到 {count} 项证据" if count else "未找到匹配证据", False
        return f"读取到 {count} 项证据" if count else "未读取到证据片段", False

    artifact = result.get("artifact")
    if isinstance(artifact, dict):
        kind = artifact.get("kind")
        if kind == "calculation" and "result" in artifact:
            value = _bounded_text(str(artifact["result"]), 80)
            return f"计算完成：{value}", False
        verdicts = artifact.get("verdicts")
        if isinstance(verdicts, list):
            statuses = [item.get("status") for item in verdicts if isinstance(item, dict)]
            supported = statuses.count("supported")
            review = statuses.count("requires_review")
            insufficient = statuses.count("insufficient_evidence")
            blocked = statuses.count("blocked_by_precondition")
            return (
                f"核查 {len(statuses)} 条结论：支持 {supported}、待复核 {review}、"
                f"证据不足 {insufficient}、前置条件阻断 {blocked}",
                False,
            )
        return "研究产物已生成", False

    status = result.get("status")
    if isinstance(status, str):
        return _bounded_text(f"返回状态：{status}", 120), False
    return "工具已返回结果", False


def _public_events(trajectory: list[dict]) -> list[PublicAgentEvent]:
    events: list[PublicAgentEvent] = []
    current_turn = 0
    for item in trajectory:
        if not isinstance(item, dict):
            continue
        turn = item.get("turn")
        if item.get("event") == "planner":
            if type(turn) is not int or not 1 <= turn <= 20:
                continue
            current_turn = turn
            events.append(
                PublicAgentEvent(
                    event="planning",
                    turn=turn,
                    status="planned",
                    result_summary=f"第 {turn} 轮工具规划已返回",
                )
            )
            continue
        if item.get("event") != "tool":
            continue
        if type(turn) is not int:
            turn = current_turn
        if not 1 <= turn <= 20:
            continue

        raw_tool = item.get("name")
        tool = raw_tool if raw_tool in PUBLIC_TOOL_NAMES else "unknown_tool"
        result_summary, failed = _result_summary(tool, item.get("result"))
        cached = item.get("cached") is True
        status = "failed" if failed else "cached" if cached else "completed"
        parameter_summary = (
            _argument_summary(tool, item["arguments"])
            if isinstance(item.get("arguments"), dict)
            else ""
        )
        events.append(
            PublicAgentEvent(
                event="tool",
                turn=turn,
                tool=tool,
                parameter_summary=parameter_summary,
                status=status,
                result_summary=result_summary,
                cached=cached,
            )
        )
    return events


def _public_artifacts(artifacts: list[dict]) -> list[PublicAgentArtifact]:
    """Keep only claim-verification fields rendered by the client."""
    public: list[PublicAgentArtifact] = []
    allowed_kinds = {"verbatim", "numeric", "code_execution", "inference"}
    allowed_statuses = {
        "supported",
        "requires_review",
        "insufficient_evidence",
        "blocked_by_precondition",
    }

    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("kind") != "claim_verification":
            continue
        raw_verdicts = artifact.get("verdicts")
        if not isinstance(raw_verdicts, list):
            continue

        verdicts: list[PublicClaimVerdict] = []
        for verdict in raw_verdicts[:12]:
            if not isinstance(verdict, dict):
                continue
            claim = verdict.get("claim")
            if not isinstance(claim, dict):
                continue
            statement = _bounded_text(claim.get("statement"), 2000)
            kind = claim.get("kind")
            status = verdict.get("status")
            if (
                not statement
                or not isinstance(kind, str)
                or kind not in allowed_kinds
                or not isinstance(status, str)
                or status not in allowed_statuses
            ):
                continue

            evidence: list[PublicEvidenceResult] = []
            raw_evidence = verdict.get("evidence")
            if isinstance(raw_evidence, list):
                for item in raw_evidence[:8]:
                    if not isinstance(item, dict):
                        continue
                    bounded = dict(item)
                    if isinstance(bounded.get("text"), str):
                        bounded["text"] = bounded["text"][:6000]
                    try:
                        evidence.append(PublicEvidenceResult.model_validate(bounded))
                    except ValidationError:
                        continue

            evidence_ids = claim.get("evidence_ids")
            safe_ids = (
                [item[:256] for item in evidence_ids[:8] if isinstance(item, str)]
                if isinstance(evidence_ids, list)
                else []
            )
            try:
                verdicts.append(
                    PublicClaimVerdict(
                        status=status,
                        claim=PublicClaimText(
                            statement=statement,
                            kind=kind,
                            evidence_ids=safe_ids,
                        ),
                        evidence=evidence,
                    )
                )
            except ValidationError:
                continue

        if verdicts:
            public.append(
                PublicAgentArtifact(kind="claim_verification", verdicts=verdicts)
            )
        if len(public) >= 20:
            break
    return public


def to_public_agent_response(response: AgentResponse) -> PublicAgentResponse:
    payload = response.model_dump(mode="python")
    payload["trajectory"] = _public_events(response.trajectory)
    payload["artifacts"] = _public_artifacts(response.artifacts)
    return PublicAgentResponse.model_validate(payload)
