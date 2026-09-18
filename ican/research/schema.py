from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ican.retrieval.schema import EvidenceResult

ClaimKind = Literal["verbatim", "numeric", "code_execution", "inference"]
ClaimStatus = Literal[
    "supported",
    "insufficient_evidence",
    "blocked_by_precondition",
    "requires_review",
]


class NumericCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=256)


class CalculationResult(NumericCalculation):
    result: str


class CodeCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1, max_length=256)
    bindings: dict[str, int | float] = Field(min_length=1, max_length=16)

    @field_validator("bindings")
    @classmethod
    def bounded_numeric_bindings(cls, values):
        for key, value in values.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError("Condition binding names must be Python identifiers")
            if (
                type(value) not in {int, float}
                or (type(value) is float and not math.isfinite(value))
                or abs(value) > 1e18
            ):
                raise ValueError("Condition bindings must be finite bounded numbers")
        return values


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=2000)
    kind: ClaimKind
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    quote: str | None = Field(default=None, min_length=1, max_length=1000)
    calculation: NumericCalculation | None = None
    conditions: list[CodeCondition] = Field(default_factory=list, max_length=8)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Evidence IDs must not repeat")
        return values

    @model_validator(mode="after")
    def kind_specific_fields(self):
        expected = {
            "verbatim": (
                self.quote is not None,
                not self.conditions and self.calculation is None,
            ),
            "numeric": (
                self.calculation is not None,
                self.quote is None and not self.conditions,
            ),
            "code_execution": (
                bool(self.conditions),
                self.quote is None and self.calculation is None,
            ),
            "inference": (
                self.quote is None,
                self.calculation is None and not self.conditions,
            ),
        }
        required, exclusive = expected[self.kind]
        if not required or not exclusive:
            raise ValueError("Claim fields do not match its kind")
        return self


class ConditionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    line: int | None = None
    expression: str
    status: Literal["passed", "failed", "unsupported"]
    diagnostic: str | None = None


class ClaimVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: ClaimDraft
    status: ClaimStatus
    evidence: list[EvidenceResult]
    conditions: list[ConditionVerdict] = Field(default_factory=list)
    calculation: CalculationResult | None = None
    diagnostics: list[str] = Field(default_factory=list)


class ClaimVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[ClaimVerdict]
