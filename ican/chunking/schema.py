from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ican.ingestion.schema import StructureSpan


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    kind: Literal["parsed", "qasper"]
    parent_manifest: str
    expected_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    inputs: dict[str, str]
    sources: str | None = None
    output_dir: str


class ChunkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    tokenizer: Literal["cl100k_base"] = "cl100k_base"
    max_tokens: int = Field(default=768, ge=32)
    max_context_tokens: int = Field(default=128, ge=0)
    overlap_tokens: int = Field(default=64, ge=0)
    datasets: list[DatasetConfig]

    @model_validator(mode="after")
    def validate_budget(self):
        if self.max_context_tokens + self.overlap_tokens + 8 >= self.max_tokens:
            raise ValueError("Context and overlap leave no usable body budget")
        if len({d.dataset_id for d in self.datasets}) != len(self.datasets):
            raise ValueError("Duplicate dataset IDs")
        if any(not d.inputs for d in self.datasets):
            raise ValueError("Input allowlist cannot be empty")
        return self


class ParentUnit(BaseModel):
    unit_id: str
    source_id: str
    source_type: Literal["paper", "code", "config", "documentation"]
    input_path: str
    path: str
    source_url: str
    version: str
    source_sha256: str | None = None
    text: str
    text_sha256: str
    location: dict
    structures: list[StructureSpan] = Field(default_factory=list)
    title: str = ""
    metadata: dict = Field(default_factory=dict)


class Region(BaseModel):
    char_start: int
    char_end: int
    kind: str
    name: str = ""
    context: list[str] = Field(default_factory=list)
    review_required: bool = False


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    chunk_id: str
    dataset_id: str
    split: str
    parent_unit_id: str
    source_id: str
    source_type: Literal["paper", "code", "config", "documentation"]
    source_path: str
    source_url: str
    source_version: str
    source_sha256: str | None
    parent_text_sha256: str
    parent_input_path: str
    text: str
    text_sha256: str
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    location: dict
    structure_kind: str
    structure_name: str
    context_path: list[str]
    provenance: list[dict]
    review_required: bool
    embedding_context: str
    embedding_text: str
    text_tokens: int = Field(gt=0)
    embedding_tokens: int = Field(gt=0)
    tokenizer: str
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_chunk(self):
        if self.char_end <= self.char_start or self.char_end - self.char_start != len(
            self.text
        ):
            raise ValueError("Chunk text length does not match parent range")
        if not self.text.strip():
            raise ValueError("Empty chunk")
        expected = (
            self.embedding_context + "\n\n" + self.text
            if self.embedding_context
            else self.text
        )
        if self.embedding_text != expected:
            raise ValueError(
                "Embedding text must keep context separate from original excerpt"
            )
        if self.source_type == "paper":
            if not (self.location.get("page") or self.location.get("paper_id")):
                raise ValueError(
                    "Paper needs a physical page or external paper/paragraph location"
                )
        elif not (self.location.get("line_start") and self.location.get("line_end")):
            raise ValueError("Repository excerpt needs a line range")
        return self
