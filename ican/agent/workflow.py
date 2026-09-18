"""Submission contracts for the mandatory claim-verification workflow."""

import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ican.research.schema import ClaimDraft

from .prompts import DRAFT_SYSTEM
from .schema import ToolInputError


class AnswerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    claims: list[ClaimDraft] = Field(min_length=1, max_length=8)

    @field_validator("evidence_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Submission evidence IDs must not repeat")
        return values

    def validate_selection(self, retained: set[str], required_kinds: list[str]):
        selected = set(self.evidence_ids)
        if not selected <= retained:
            raise ToolInputError("Submission evidence must be retained in this task")
        cited = {cid for claim in self.claims for cid in claim.evidence_ids}
        if not cited <= selected:
            raise ToolInputError(
                "Claim evidence must be selected for the final context"
            )
        if not set(required_kinds) <= {claim.kind for claim in self.claims}:
            raise ToolInputError("Submission is missing a required claim kind")


INVESTIGATION_TOOLS = {
    "search_evidence",
    "read_evidence",
    "trace_config",
    "calculate",
    "submit_claims",
}


def submission_tool_schema():
    """Expose kind-specific fields instead of only runtime-only validators."""
    schema = AnswerSubmission.model_json_schema()
    template = schema["$defs"]["ClaimDraft"]
    variants = []
    for kind, required_field in (
        ("verbatim", "quote"),
        ("numeric", "calculation"),
        ("code_execution", "conditions"),
        ("inference", None),
    ):
        variant = deepcopy(template)
        fields = {"statement", "kind", "evidence_ids"}
        if required_field:
            fields.add(required_field)
        variant["properties"] = {
            name: value
            for name, value in variant["properties"].items()
            if name in fields
        }
        variant["properties"]["kind"] = {"type": "string", "const": kind}
        if required_field:
            variant["required"].append(required_field)
            field = variant["properties"][required_field]
            field.pop("default", None)
            if "anyOf" in field:
                variant["properties"][required_field] = next(
                    value for value in field["anyOf"] if value.get("type") != "null"
                )
            elif required_field == "conditions":
                field["minItems"] = 1
        variants.append(variant)
    schema["properties"]["claims"]["items"] = {"oneOf": variants}
    schema["$defs"].pop("ClaimDraft")
    return schema


def draft_messages(request, evidence_pool, artifacts):
    """Build a fresh draft context without previous tool names or call history."""
    return [
        {"role": "system", "content": DRAFT_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": request.model_dump(mode="json"),
                    "evidence": [
                        evidence.model_dump(mode="json")
                        for evidence in evidence_pool.values()
                    ],
                    "tool_artifacts": artifacts,
                },
                ensure_ascii=False,
            ),
        },
    ]
