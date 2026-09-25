from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ican.qa.schema import QAResponse
from ican.retrieval.schema import EvidenceResult, SearchRequest


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["p4-agent-v1", "p4-agent-v2"] = "p4-agent-v1"
    workflow_mode: Literal["tool_loop", "verified"] = "tool_loop"
    planner_model: Literal["deepseek-v4-pro", "deepseek-flash"] = "deepseek-v4-pro"
    answer_model: Literal["deepseek-flash", "deepseek-v4-pro"] = "deepseek-flash"
    max_planner_calls: int = Field(default=5, ge=1, le=8)
    max_tool_calls: int = Field(default=12, ge=1, le=20)
    max_evidence_pool: int = Field(default=32, ge=8, le=40)
    model_timeout_seconds: float = Field(default=60, gt=0, le=90)
    task_timeout_seconds: float = Field(default=180, gt=0, le=300)
    planner_max_tokens: int = Field(default=1536, ge=128, le=2048)

    @model_validator(mode="after")
    def reserve_submission_turn(self):
        if self.workflow_mode == "verified" and self.max_planner_calls < 2:
            raise ValueError(
                "Verified workflow requires investigation and submission turns"
            )
        return self


class UserOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opts: list[Annotated[str, Field(max_length=1024)]] = Field(
        default_factory=list, max_length=20
    )
    cli: dict = Field(default_factory=dict, max_length=10)

    @field_validator("opts")
    @classmethod
    def paired_opts(cls, values):
        if len(values) % 2:
            raise ValueError("opts must contain alternating field/value pairs")
        return values

    @field_validator("cli")
    @classmethod
    def bounded_cli_scalars(cls, values):
        for key, value in values.items():
            if (
                not isinstance(key, str)
                or len(key) > 64
                or type(value) not in {str, int, float, bool}
            ):
                raise ValueError("CLI values must be bounded scalar values")
            if isinstance(value, str) and len(value) > 1024:
                raise ValueError("CLI strings exceed bounds")
            if type(value) in {int, float} and (
                abs(value) > 1e18 or (type(value) is float and not math.isfinite(value))
            ):
                raise ValueError("CLI numbers exceed finite bounds")
        return values


class AgentRequest(SearchRequest):
    limit: int = Field(default=8, ge=1, le=8)
    strategy: Literal["dense", "dense_scoped", "bm25", "hybrid", "hybrid_rerank"] = (
        "hybrid_rerank"
    )
    user_overrides: UserOverrides = Field(default_factory=UserOverrides)
    required_claim_kinds: list[
        Literal["verbatim", "numeric", "code_execution", "inference"]
    ] = Field(default_factory=list, max_length=4)

    @field_validator("required_claim_kinds")
    @classmethod
    def unique_claim_kinds(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Required claim kinds must not repeat")
        return values


class AgentUsage(BaseModel):
    paid_calls: int = 0
    planner_calls: int = 0
    answer_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    usage_missing_calls: int = 0
    actual_cost_usd: float | None = None


class AgentResponse(BaseModel):
    task_id: str
    status: Literal[
        "completed",
        "insufficient_evidence",
        "review_required",
        "budget_exhausted",
        "no_progress",
        "failed",
        "timed_out",
    ]
    stop_reason: str
    answer: QAResponse | None = None
    artifacts: list[dict] = Field(default_factory=list)
    trajectory: list[dict] = Field(default_factory=list)
    workflow_mode: Literal["tool_loop", "verified"] = "tool_loop"
    workflow_stages: list[dict] = Field(default_factory=list)
    usage: AgentUsage = Field(default_factory=AgentUsage)
    index_fingerprint: str | None = None
    paperqa_version: str = "2026.8.12"
    planner_model: str
    answer_model: str


class PublicAgentEvent(BaseModel):
    """A bounded Agent trace event safe to return to the web client."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["planning", "tool"]
    turn: int = Field(ge=1, le=20)
    tool: str | None = Field(default=None, max_length=64)
    parameter_summary: str = Field(default="", max_length=240)
    status: Literal["planned", "completed", "cached", "failed"] | None = None
    result_summary: str = Field(default="", max_length=240)
    cached: bool = False


class PublicClaimText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=2000)
    kind: Literal["verbatim", "numeric", "code_execution", "inference"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)


class PublicEvidenceResult(EvidenceResult):
    text: str = Field(max_length=6000)


class PublicClaimVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "supported",
        "requires_review",
        "insufficient_evidence",
        "blocked_by_precondition",
    ]
    claim: PublicClaimText
    evidence: list[PublicEvidenceResult] = Field(default_factory=list, max_length=8)


class PublicAgentArtifact(BaseModel):
    """The user-facing claim checks needed for evidence review."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["claim_verification"]
    verdicts: list[PublicClaimVerdict] = Field(max_length=12)


class PublicAgentResponse(AgentResponse):
    """HTTP response shape with private planner and raw tool data removed."""

    artifacts: list[PublicAgentArtifact] = Field(default_factory=list, max_length=20)
    trajectory: list[PublicAgentEvent] = Field(default_factory=list)


class ToolInputError(ValueError):
    """A bounded public tool validation error."""


class BudgetExhausted(RuntimeError):
    """A paid or local tool budget was exhausted before dispatch."""
