"""Contracts shared by parsers and downstream chunking."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceSpec(BaseModel):
    kind: Literal["paper", "repository"]
    path: str
    version: str
    url: str
    expected_sha256: str | None = None


class IngestionConfig(BaseModel):
    dataset_id: str
    output_dir: str
    max_file_bytes: int = Field(default=2_097_152, gt=0)
    extensions: list[str]
    filenames: list[str] = Field(default_factory=list)
    sources: list[SourceSpec]
    pdf_backend: Literal["pymupdf", "docling"] = "pymupdf"


class StructureSpan(BaseModel):
    kind: str
    name: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    bbox: list[float] | None = None
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> StructureSpan:
        if self.line_end < self.line_start or self.char_end < self.char_start:
            raise ValueError("Reversed structure range")
        return self


class ParsedUnit(BaseModel):
    unit_id: str
    source_id: str
    source_type: Literal["paper", "code", "config", "documentation"]
    path: str
    version: str
    text: str
    text_sha256: str
    page: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    structures: list[StructureSpan] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_location(self) -> ParsedUnit:
        if self.source_type == "paper":
            if self.page is None:
                raise ValueError("Paper units require a physical PDF page")
        elif self.line_start is None or self.line_end is None:
            raise ValueError("Repository units require a file line range")
        elif self.line_end < self.line_start:
            raise ValueError("Reversed file line range")
        if any(span.char_end > len(self.text) for span in self.structures):
            raise ValueError("Structure outside original text")
        return self


class SourceRecord(BaseModel):
    source_id: str
    kind: Literal["paper", "repository"]
    path: str
    version: str
    url: str
    raw_sha256: str
    status: Literal["parsed", "partial", "empty", "failed"]
    unit_count: int
    metadata: dict = Field(default_factory=dict)
