"""Deterministic diagnostics for one-call research-card submissions."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .auto_schema import CardModelDraft


class SubmissionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    path: list[str | int] = Field(default_factory=list)
    message: str


class SubmissionDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected"]
    code: str
    issues: list[SubmissionIssue] = Field(default_factory=list)
    referenced_evidence_ids: list[str] = Field(default_factory=list)
    unknown_evidence_ids: list[str] = Field(default_factory=list)
    draft: CardModelDraft | None = None

    def error_message(self) -> str:
        if self.status == "accepted":
            return "accepted"
        summary = "; ".join(
            f"{'.'.join(map(str, issue.path)) or 'action'}: {issue.message}"
            for issue in self.issues[:3]
        )
        return f"Research card submission failed [{self.code}]: {summary}"


def _reject(code: str, message: str, *, path=(), issues=None, **kwargs):
    return SubmissionDiagnosis(
        status="rejected",
        code=code,
        issues=issues or [SubmissionIssue(code=code, path=list(path), message=message)],
        **kwargs,
    )


def diagnose_card_submission(
    action: Any, allowed_evidence_ids: set[str]
) -> SubmissionDiagnosis:
    """Parse a model action without collapsing distinct protocol failures."""

    if not isinstance(action, dict):
        return _reject("malformed_action", "model action must be an object")
    calls = action.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return _reject(
            "no_tool_call", "model did not call a tool", path=("tool_calls",)
        )
    if len(calls) != 1:
        return _reject(
            "multiple_tool_calls",
            f"expected one tool call, received {len(calls)}",
            path=("tool_calls",),
        )
    call = calls[0]
    function = call.get("function") if isinstance(call, dict) else None
    if not isinstance(function, dict):
        return _reject(
            "malformed_tool_call",
            "tool call must contain a function object",
            path=("tool_calls", 0, "function"),
        )
    if function.get("name") != "submit_research_card":
        return _reject(
            "wrong_tool_name",
            "expected submit_research_card",
            path=("tool_calls", 0, "function", "name"),
        )
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        return _reject(
            "arguments_not_string",
            "tool arguments must be a JSON string",
            path=("tool_calls", 0, "function", "arguments"),
        )
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as error:
        return _reject(
            "invalid_json",
            f"invalid JSON at line {error.lineno}, column {error.colno}",
            path=("tool_calls", 0, "function", "arguments"),
        )
    try:
        draft = CardModelDraft.model_validate(payload)
    except ValidationError as error:
        issues = [
            SubmissionIssue(
                code="schema_invalid",
                path=list(item["loc"]),
                message=item["msg"],
            )
            for item in error.errors(include_input=False, include_url=False)
        ]
        return _reject("schema_invalid", "tool arguments violate schema", issues=issues)
    referenced = sorted(
        set(draft.reason_evidence_ids) | {field.evidence_id for field in draft.fields}
    )
    unknown = sorted(set(referenced) - allowed_evidence_ids)
    if unknown:
        return _reject(
            "evidence_out_of_scope",
            "submission cites evidence outside the selected paper",
            path=("evidence_ids",),
            referenced_evidence_ids=referenced,
            unknown_evidence_ids=unknown,
        )
    return SubmissionDiagnosis(
        status="accepted",
        code="accepted",
        draft=draft,
        referenced_evidence_ids=referenced,
    )
