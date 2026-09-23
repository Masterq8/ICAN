"""Project model fields into usable facts and paper-scoped review candidates."""

from __future__ import annotations

import json
from collections.abc import Iterable

from ican.retrieval.schema import EvidenceResult

from .auto_schema import CardFieldDraft, HighConfidenceField, ReviewCandidate
from .field_rules import diagnose_field_assignment


def recover_fields(action: dict | None) -> list[CardFieldDraft]:
    """Recover individually valid fields from an otherwise rejected tool action."""

    if not isinstance(action, dict):
        return []
    calls = action.get("tool_calls")
    if not isinstance(calls, list):
        return []
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else None
        if (
            not isinstance(function, dict)
            or function.get("name") != "submit_research_card"
        ):
            continue
        arguments = function.get("arguments")
        try:
            payload = json.loads(arguments) if isinstance(arguments, str) else arguments
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict) or not isinstance(payload.get("fields"), list):
            return []
        recovered = []
        for item in payload["fields"][:36]:
            try:
                recovered.append(CardFieldDraft.model_validate(item))
            except ValueError:
                continue
        return recovered
    return []


def project_fields(
    source_id: str,
    evidence: Iterable[EvidenceResult],
    fields: Iterable[CardFieldDraft],
) -> tuple[list[HighConfidenceField], list[ReviewCandidate]]:
    evidence_by_id = {item.chunk_id: item for item in evidence}
    high: list[HighConfidenceField] = []
    review: list[ReviewCandidate] = []
    for occurrence, field in enumerate(fields):
        reasons: list[str] = []
        item = evidence_by_id.get(field.evidence_id)
        if item is None or item.source.source_id != source_id:
            reasons.append("evidence_out_of_scope")
        elif field.quote not in item.text:
            reasons.append("quote_not_exact")
        elif field.value not in field.quote:
            reasons.append("value_not_in_quote")
        diagnostics = diagnose_field_assignment(field.name, field.value, field.quote)
        reasons.extend(f"field_rule:{item.code}" for item in diagnostics)
        payload = {
            "occurrence": occurrence,
            "source_id": source_id,
            "name": field.name,
            "value": field.value,
            "quote": field.quote,
            "evidence_id": field.evidence_id,
        }
        if reasons:
            review.append(
                ReviewCandidate(
                    **payload,
                    reason_codes=reasons,
                    reason="；".join(_reason_text(reason) for reason in reasons),
                )
            )
        else:
            high.append(
                HighConfidenceField(
                    **payload,
                    confidence_reasons=[
                        "same_paper_evidence",
                        "exact_contiguous_quote",
                        "no_field_rule_conflict",
                    ],
                )
            )
    return high, review


def _reason_text(code: str) -> str:
    if code == "evidence_out_of_scope":
        return "证据不属于当前论文"
    if code == "quote_not_exact":
        return "引文不是当前证据中的连续原文"
    if code == "value_not_in_quote":
        return "字段值不是所引连续原文中的字面子串"
    if code.startswith("field_rule:"):
        return "字段类型触发确定性冲突规则：" + code.split(":", 1)[1]
    return code
