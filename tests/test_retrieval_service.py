from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from qdrant_client import models

from ican.indexing.schema import IndexConfig
from ican.retrieval import service as retrieval_service
from ican.retrieval.schema import SearchFilters, SearchRequest
from ican.retrieval.service import (
    CollectionNotFound,
    EvidenceSearchService,
    IndexUnavailable,
)


def config() -> IndexConfig:
    return IndexConfig.model_validate(
        {
            "model": {
                "repository": "BAAI/bge-m3",
                "revision": "a" * 40,
                "local_path": "data/cache/model",
                "ledger_path": "data/catalog/model.json",
                "files": {"config.json": {"size": 1, "sha256": "a" * 64}},
                "device": "cpu",
                "precision": "float32",
            },
            "chunk_config": "configs/chunking/v1.json",
            "storage_root": "data/indexes/test",
            "sources": [
                {
                    "dataset_id": "d",
                    "directory": "data/processed/chunks",
                    "expected_manifest_sha256": "b" * 64,
                    "collections": {"default": "swin_v1"},
                }
            ],
        }
    )


class FakeEncoder:
    def encode(self, texts: list[str]) -> np.ndarray:
        assert texts == ["window size"]
        vector = np.zeros((1, 1024), dtype=np.float32)
        vector[0, 0] = 1
        return vector


class FailIfCalledEncoder:
    def encode(self, texts: list[str]) -> np.ndarray:
        raise AssertionError("unknown collection must be rejected before encoding")


class FakeClient:
    last_filter = None

    def __init__(self, *, path: str):
        self.path = path

    def close(self):
        return None

    def query_points(self, collection_name, query, query_filter, limit, **kwargs):
        type(self).last_filter = query_filter
        assert collection_name == "swin_v1"
        assert len(query) == 1024
        assert limit == 5
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.9,
                    payload={
                        "chunk": {
                            "chunk_id": "chunk-1",
                            "text": "WINDOW_SIZE: 7",
                            "review_required": False,
                            "source_id": "source-1",
                            "source_type": "config",
                            "source_path": "data/raw/repositories/Swin-Transformer/configs/swin/swin_tiny.yaml",
                            "source_version": "commit-1",
                            "location": {"line_start": 1, "line_end": 2},
                        }
                    },
                )
            ]
        )


@pytest.fixture
def service(tmp_path: Path) -> EvidenceSearchService:
    directory = tmp_path / "index"
    directory.mkdir()
    (directory / "qdrant").mkdir()
    (directory / "index_manifest.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "config": config().model_dump(),
                "collections": {"swin_v1": 1},
            }
        ),
        encoding="utf-8",
    )
    return EvidenceSearchService(
        tmp_path,
        config(),
        encoder=FakeEncoder(),
        client_factory=FakeClient,
        index_path=directory,
    )


def test_service_maps_source_type_and_path_prefix_filters(service):
    response = service.search(
        SearchRequest(
            query="window size",
            collection="swin_v1",
            filters=SearchFilters(
                source_types=["config"],
                path_prefixes=["data/raw/repositories/Swin-Transformer/configs/swin/"],
            ),
        )
    )

    assert response.results[0].source.source_path.startswith(
        "data/raw/repositories/Swin-Transformer/configs/swin/"
    )
    assert FakeClient.last_filter == models.Filter(
        must=[
            models.FieldCondition(
                key="chunk.source_type", match=models.MatchAny(any=["config"])
            )
        ],
        should=[
            models.FieldCondition(
                key="chunk.source_path",
                match=models.MatchPrefix(
                    prefix="data/raw/repositories/Swin-Transformer/configs/swin/"
                ),
            )
        ],
    )


def test_service_rejects_unknown_collection_before_encoding(tmp_path: Path):
    directory = tmp_path / "index"
    directory.mkdir()
    (directory / "qdrant").mkdir()
    (directory / "index_manifest.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "config": config().model_dump(),
                "collections": {"swin_v1": 1},
            }
        ),
        encoding="utf-8",
    )
    service = EvidenceSearchService(
        tmp_path,
        config(),
        encoder=FailIfCalledEncoder(),
        client_factory=FakeClient,
        index_path=directory,
    )

    with pytest.raises(CollectionNotFound):
        service.search(SearchRequest(query="x", collection="not_real"))


class ExclusiveClient(FakeClient):
    active = 0
    maximum_active = 0
    guard = threading.Lock()

    def __init__(self, *, path: str):
        super().__init__(path=path)
        with self.guard:
            type(self).active += 1
            type(self).maximum_active = max(
                type(self).maximum_active, type(self).active
            )

    def close(self):
        with self.guard:
            type(self).active -= 1

    def query_points(self, *args, **kwargs):
        time.sleep(0.02)
        return super().query_points(*args, **kwargs)


def test_service_serializes_local_qdrant_client_lifetimes(service):
    service.client_factory = ExclusiveClient
    ExclusiveClient.active = 0
    ExclusiveClient.maximum_active = 0
    request = SearchRequest(query="window size", collection="swin_v1")

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(lambda _: service.search(request), range(5)))

    assert len(responses) == 5
    assert ExclusiveClient.maximum_active == 1
    assert ExclusiveClient.active == 0


def test_production_service_verifies_index_identity_and_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    directory = tmp_path / "index"
    directory.mkdir()
    (directory / "qdrant").mkdir()
    identity = {"config_sha256": "a" * 64}
    (directory / "index_manifest.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "config": config().model_dump(),
                "collections": {"swin_v1": 1},
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )
    verified = []
    monkeypatch.setattr(retrieval_service, "verified_model", lambda *_: ({}, "ledger"))
    monkeypatch.setattr(retrieval_service, "load_chunks", lambda *_: ([], {"d": {}}))
    monkeypatch.setattr(retrieval_service, "index_identity", lambda *_: identity)
    monkeypatch.setattr(retrieval_service, "index_directory", lambda *_: directory)
    monkeypatch.setattr(
        retrieval_service,
        "verify_artifacts",
        lambda *args: verified.append(args),
    )
    service = EvidenceSearchService(
        tmp_path, config(), encoder=FakeEncoder(), client_factory=FakeClient
    )

    service.search(SearchRequest(query="window size", collection="swin_v1"))

    assert len(verified) == 1
    assert verified[0][3] == identity


def test_production_service_rejects_failed_artifact_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    directory = tmp_path / "index"
    directory.mkdir()
    (directory / "qdrant").mkdir()
    identity = {"config_sha256": "a" * 64}
    (directory / "index_manifest.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "config": config().model_dump(),
                "collections": {"swin_v1": 1},
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(retrieval_service, "verified_model", lambda *_: ({}, "ledger"))
    monkeypatch.setattr(retrieval_service, "load_chunks", lambda *_: ([], {"d": {}}))
    monkeypatch.setattr(retrieval_service, "index_identity", lambda *_: identity)
    monkeypatch.setattr(retrieval_service, "index_directory", lambda *_: directory)
    monkeypatch.setattr(
        retrieval_service,
        "verify_artifacts",
        lambda *_: (_ for _ in ()).throw(ValueError("tampered payload")),
    )
    service = EvidenceSearchService(
        tmp_path, config(), encoder=FakeEncoder(), client_factory=FakeClient
    )

    with pytest.raises(IndexUnavailable):
        service.search(SearchRequest(query="window size", collection="swin_v1"))
