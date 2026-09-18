from pydantic import BaseModel, ConfigDict, Field


class RetrievalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = "hybrid-v1"
    candidate_limit: int = Field(default=40, ge=20, le=80)
    rerank_limit: int = Field(default=48, ge=20, le=80)
    rrf_k: int = Field(default=60, ge=1)
    bm25_k1: float = Field(default=1.5, gt=0)
    bm25_b: float = Field(default=0.75, ge=0, le=1)
    structural_context: bool = True
    max_context_additions: int = Field(default=3, ge=0, le=5)
    reranker_config: str = "configs/reranking/v1.json"
