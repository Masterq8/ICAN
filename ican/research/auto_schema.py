"""Contracts for automatic, source-scoped paper discovery and experiment cards."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ican.retrieval.schema import EvidenceResult

from .schema import ExtractionFieldName, ResearchRecord

ProductCollection = Literal["swin_v1", "qasper_train_v1"]


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=1000)
    collection: ProductCollection
    limit: int = Field(default=4, ge=1, le=6)


class PaperCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: ProductCollection
    source_id: str
    title: str
    source_path: str
    source_version: str
    evidence: list[EvidenceResult] = Field(max_length=8)


class DiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    collection: ProductCollection
    candidates: list[PaperCandidate]
    index_fingerprint: str


class AutoCardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=1000)
    collection: ProductCollection
    source_id: str = Field(min_length=1, max_length=256)


class CardFieldDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ExtractionFieldName = Field(
        description=(
            "task=research task; model=method/system; dataset=named corpus or benchmark; "
            "input_setting=input/preprocessing; training=optimization setup; "
            "metric=measurement name without score; result=measured value or comparative "
            "finding; limitation=stated constraint; code_availability=code/repository status"
        )
    )
    value: str = Field(min_length=1, max_length=1200)
    quote: str = Field(min_length=1, max_length=1000)
    evidence_id: str = Field(min_length=1, max_length=256)


class CardModelDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["include", "exclude", "hold"]
    reason: str = Field(min_length=1, max_length=1200)
    reason_evidence_ids: list[str] = Field(min_length=1, max_length=3)
    fields: list[CardFieldDraft] = Field(
        min_length=1,
        max_length=36,
        description="Ordered entries; names may repeat. Each entry retains its own value and evidence. Maximum 36 entries.",
    )

    @field_validator("reason_evidence_ids")
    @classmethod
    def no_duplicate_reason_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Reason evidence IDs must not repeat")
        return value


class LegacyCardModelDraft(CardModelDraft):
    """Frozen v1 protocol for historical audit only."""

    fields: list[CardFieldDraft] = Field(min_length=1, max_length=9)

    @field_validator("fields")
    @classmethod
    def no_duplicate_fields(cls, value):
        if len({field.name for field in value}) != len(value):
            raise ValueError("Experiment field names must not repeat")
        return value


class CardUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_calls: int
    prompt_tokens: int
    completion_tokens: int
    actual_cost_usd: None = None


class AutoCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: PaperCandidate
    screening: ResearchRecord
    extraction: ResearchRecord | None
    usage: CardUsage


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_ids: list[UUID] = Field(min_length=2, max_length=4)

    @field_validator("record_ids")
    @classmethod
    def no_duplicate_records(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Comparison record IDs must not repeat")
        return value


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_ids: list[UUID]
    comparable: bool
    warnings: list[str]
    markdown: str
