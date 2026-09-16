"""Run local smoke tests for the ICAN development environment."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

import jieba
import pymupdf
import torch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi


ROOT = Path(__file__).resolve().parents[1]


def check_gpu() -> None:
    assert torch.cuda.is_available(), "CUDA is not available to PyTorch"
    left = torch.randn(256, 256, device="cuda")
    right = torch.randn(256, 256, device="cuda")
    result = left @ right
    assert result.shape == (256, 256)
    print(f"[PASS] CUDA: {torch.cuda.get_device_name(0)}")


def check_pdf() -> None:
    pdf_path = ROOT / "data/raw/papers/swin_transformer_2103.14030.pdf"
    with pymupdf.open(pdf_path) as document:
        first_page = document[0].get_text()
        assert len(document) > 1 and "Swin Transformer" in first_page
        print(f"[PASS] PDF parsing: {len(document)} pages")


def check_qdrant() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="smoke",
        vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
    )
    client.upsert(
        collection_name="smoke",
        points=[
            models.PointStruct(id=1, vector=[1.0, 0.0, 0.0], payload={"name": "swin"}),
            models.PointStruct(id=2, vector=[0.0, 1.0, 0.0], payload={"name": "mamba"}),
        ],
    )
    hits = client.query_points(
        collection_name="smoke", query=[0.9, 0.1, 0.0], limit=1
    ).points
    assert hits[0].payload["name"] == "swin"
    print("[PASS] Qdrant local vector search")


def check_bm25() -> None:
    documents = ["Swin 使用 移位窗口 注意力", "Mamba 使用 状态空间 模型"]
    tokenized = [list(jieba.cut(item)) for item in documents]
    engine = BM25Okapi(tokenized)
    scores = engine.get_scores(list(jieba.cut("Swin 窗口 注意力")))
    assert int(scores.argmax()) == 0
    print("[PASS] BM25 sparse retrieval")


class GraphState(TypedDict):
    value: int


def check_langgraph() -> None:
    graph = StateGraph(GraphState)
    graph.add_node("increment", lambda state: {"value": state["value"] + 1})
    graph.add_edge(START, "increment")
    graph.add_edge("increment", END)
    result = graph.compile().invoke({"value": 1})
    assert result == {"value": 2}
    print("[PASS] LangGraph state transition")


def check_fastapi() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(app).get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    print("[PASS] FastAPI test client")


def check_swin() -> None:
    repository = ROOT / "data/raw/repositories/Swin-Transformer"
    sys.path.insert(0, str(repository))
    from models.swin_transformer import SwinTransformer

    model = SwinTransformer(
        img_size=224,
        patch_size=4,
        in_chans=3,
        num_classes=1000,
        embed_dim=96,
        depths=[2, 2, 6, 2],
        num_heads=[3, 6, 12, 24],
        window_size=7,
    )
    checkpoint_path = ROOT / "data/raw/weights/swin_tiny_patch4_window7_224.pth"
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    state_dict = checkpoint.get("model", checkpoint)
    model.load_state_dict(state_dict, strict=True)
    model = model.eval().cuda()
    with torch.inference_mode():
        output = model(torch.randn(1, 3, 224, 224, device="cuda"))
    assert output.shape == (1, 1000)
    print("[PASS] Official Swin-T checkpoint and CUDA forward pass")


def main() -> None:
    check_gpu()
    check_pdf()
    check_qdrant()
    check_bm25()
    check_langgraph()
    check_fastapi()
    check_swin()
    print("ALL_SMOKE_TESTS_PASSED")


if __name__ == "__main__":
    main()
