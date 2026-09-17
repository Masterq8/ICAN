from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FileIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: int = Field(gt=0)
    sha256: str | None = None
    git_blob_sha1: str | None = None

    @model_validator(mode="after")
    def identity_required(self):
        if not (self.sha256 or self.git_blob_sha1):
            raise ValueError("Model file requires an upstream content identity")
        return self


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: Literal["BAAI/bge-m3"]
    revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    local_path: str
    ledger_path: str
    files: dict[str, FileIdentity]
    dimension: Literal[1024] = 1024
    max_sequence_length: Literal[8192] = 8192
    device: Literal["cuda", "cpu"] = "cuda"
    precision: Literal["float16", "float32"] = "float16"
    batch_size: int = Field(default=8, ge=1, le=128)

    @model_validator(mode="after")
    def safe_precision(self):
        if self.device == "cpu" and self.precision != "float32":
            raise ValueError("CPU encoding requires float32")
        if not self.files:
            raise ValueError("No fixed model files")
        return self


class ChunkSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    directory: str
    expected_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    collections: dict[str, str]


class IndexConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    model: ModelConfig
    chunk_config: str
    storage_root: str
    document_template: Literal["chunk.embedding_text"] = "chunk.embedding_text"
    query_template: Literal["raw_text"] = "raw_text"
    normalize_embeddings: Literal[True] = True
    distance: Literal["Cosine"] = "Cosine"
    sources: list[ChunkSource]
    evaluation_sha256: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def disjoint(self):
        if not self.sources or len({s.dataset_id for s in self.sources}) != len(
            self.sources
        ):
            raise ValueError("Sources must be nonempty and unique")
        names = [c for s in self.sources for c in s.collections.values()]
        if len(set(names)) != len(names) or any(
            not s.collections for s in self.sources
        ):
            raise ValueError("Collections must be nonempty and disjoint")
        return self
