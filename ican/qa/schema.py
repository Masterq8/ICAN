from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ican.retrieval.schema import EvidenceResult, SearchRequest


class QAConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paperqa_version: Literal["2026.8.12"] = "2026.8.12"
    prompt_version: Literal["swin-evidence-v2"] = "swin-evidence-v2"
    max_evidence: int = Field(default=8, ge=1, le=8)
    max_context_chars: int = Field(default=18000, ge=1, le=18000)
    max_output_tokens: int = Field(default=1536, ge=1, le=1536)
    timeout_seconds: float = Field(default=90, gt=0, le=90)


class QARequest(SearchRequest):
    limit: int = Field(default=8, ge=1, le=8)


class Citation(BaseModel):
    number: int
    context_id: str
    evidence: EvidenceResult


class Usage(BaseModel):
    generation_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None  # No inferred pricing; unknown is not zero.


class QAResponse(BaseModel):
    status: Literal[
        "answered", "insufficient_evidence", "citation_invalid", "review_required"
    ]
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    invalid_citation_ids: list[str] = Field(default_factory=list)
    included_chunk_ids: list[str] = Field(default_factory=list)
    dropped_chunk_ids: list[str] = Field(default_factory=list)
    index_fingerprint: str
    collection: str
    model: str | None = None
    paperqa_version: str
    prompt_version: str
    usage: Usage = Field(default_factory=Usage)
