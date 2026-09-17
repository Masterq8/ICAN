from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal["paper", "code", "config", "documentation"]


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_types: list[SourceType] | None = Field(default=None, max_length=4)
    path_prefixes: list[str] | None = Field(default=None, max_length=20)

    @field_validator("source_types")
    @classmethod
    def unique_source_types(cls, values: list[SourceType] | None):
        if values is not None and len(set(values)) != len(values):
            raise ValueError("source types must not repeat")
        return values

    @field_validator("path_prefixes")
    @classmethod
    def safe_prefixes(cls, values: list[str] | None):
        if values is None:
            return values
        for prefix in values:
            path = PurePosixPath(prefix)
            if (
                not prefix
                or "\\" in prefix
                or prefix.startswith("/")
                or ":" in prefix
                or ".." in path.parts
            ):
                raise ValueError("path prefix must be a nonempty relative POSIX path")
        if len(set(values)) != len(values):
            raise ValueError("path prefixes must not repeat")
        return values


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4096)
    collection: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=5, ge=1, le=20)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: SourceType
    source_path: str
    source_version: str
    location: dict


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    score: float
    chunk_id: str
    text: str
    review_required: bool
    source: EvidenceSource


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_fingerprint: str
    collection: str
    query: str
    filters: SearchFilters
    results: list[EvidenceResult]
