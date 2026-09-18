from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from threading import Lock

from qdrant_client import QdrantClient, models

from ican.indexing.inputs import load_chunks
from ican.indexing.model import DenseEncoder, verified_model
from ican.indexing.pipeline import index_directory, index_identity
from ican.indexing.schema import IndexConfig
from ican.indexing.verification import verify_artifacts

from .schema import EvidenceResult, EvidenceSource, SearchRequest, SearchResponse

LOGGER = logging.getLogger("ican.retrieval")


class IndexUnavailable(RuntimeError):
    """The immutable local index cannot be safely served."""


class CollectionNotFound(ValueError):
    """The request selected no collection in the verified index."""


class EvidenceSearchService:
    """Read-only dense search against one immutable local Qdrant index version."""

    def __init__(
        self,
        root: Path,
        config: IndexConfig,
        *,
        encoder=None,
        client_factory: Callable[..., QdrantClient] = QdrantClient,
        index_path: Path | None = None,
    ):
        self.root = root.resolve()
        self.config = config
        self.encoder = encoder
        self.client_factory = client_factory
        self._index_path = index_path
        self._manifest: dict | None = None
        self._initialization_lock = Lock()
        self._encoder_lock = Lock()
        self._query_lock = Lock()

    def _load_index(self) -> tuple[Path, dict]:
        if self._manifest is not None and self._index_path is not None:
            return self._index_path, self._manifest
        with self._initialization_lock:
            if self._manifest is not None and self._index_path is not None:
                return self._index_path, self._manifest
            try:
                # index_path is a deliberately unverified dependency-injection seam
                # for offline unit tests. Production always derives and verifies it.
                if self._index_path is not None:
                    manifest_path = self._index_path / "index_manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                else:
                    _, ledger_hash = verified_model(self.root, self.config.model)
                    rows, snapshots = load_chunks(self.root, self.config)
                    identity = index_identity(self.config, snapshots, ledger_hash)
                    self._index_path = index_directory(self.root, self.config, identity)
                    manifest_path = self._index_path / "index_manifest.json"
                    with self._query_lock:
                        verify_artifacts(self._index_path, rows, self.config, identity)
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest.get("identity") != identity:
                        raise IndexUnavailable(
                            "Verified local index identity is invalid"
                        )
                qdrant_path = self._index_path / "qdrant"
                if (
                    not qdrant_path.is_dir()
                    or manifest.get("status") != "passed"
                    or manifest.get("config") != self.config.model_dump()
                    or not isinstance(manifest.get("collections"), dict)
                ):
                    raise IndexUnavailable("Verified local index manifest is invalid")
                self._manifest = manifest
                return self._index_path, manifest
            except IndexUnavailable:
                raise
            except (OSError, ValueError, json.JSONDecodeError, KeyError) as error:
                raise IndexUnavailable("Verified local index is unavailable") from error

    @staticmethod
    def _query_filter(request: SearchRequest) -> models.Filter | None:
        must = []
        should = []
        if request.filters.source_types:
            must.append(
                models.FieldCondition(
                    key="chunk.source_type",
                    match=models.MatchAny(any=request.filters.source_types),
                )
            )
        for prefix in request.filters.path_prefixes or []:
            should.append(
                models.FieldCondition(
                    key="chunk.source_path",
                    match=models.MatchPrefix(prefix=prefix),
                )
            )
        if not must and not should:
            return None
        return models.Filter(must=must or None, should=should or None)

    def _encoder(self):
        if self.encoder is None:
            with self._encoder_lock:
                if self.encoder is None:
                    self.encoder = DenseEncoder(self.root, self.config.model)
        return self.encoder

    def search(self, request: SearchRequest) -> SearchResponse:
        return self._search(request, request.limit)

    def candidates(
        self, request: SearchRequest, limit: int, allowed_point_ids: list[str]
    ) -> SearchResponse:
        if not 1 <= limit <= 80:
            raise ValueError("Internal candidate limit must be1..80")
        return self._search(request, limit, allowed_point_ids)

    def _search(
        self,
        request: SearchRequest,
        limit: int,
        allowed_point_ids: list[str] | None = None,
    ) -> SearchResponse:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        directory, manifest = self._load_index()
        if request.collection not in manifest["collections"]:
            raise CollectionNotFound("Unknown evidence collection")
        if allowed_point_ids == []:
            return SearchResponse(
                index_fingerprint=directory.name,
                collection=request.collection,
                query=request.query,
                filters=request.filters,
                results=[],
            )
        try:
            vector = self._encoder().encode([request.query])[0].tolist()
            with (
                self._query_lock,
                closing(self.client_factory(path=str(directory / "qdrant"))) as client,
            ):
                query_filter = self._query_filter(request)
                if allowed_point_ids is not None:
                    conditions = [models.HasIdCondition(has_id=allowed_point_ids)]
                    if query_filter is not None:
                        conditions.append(query_filter)
                    query_filter = models.Filter(must=conditions)
                found = client.query_points(
                    collection_name=request.collection,
                    query=vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                ).points
        except IndexUnavailable:
            raise
        except Exception as error:
            raise IndexUnavailable("Evidence query failed") from error
        results = []
        for rank, point in enumerate(found, start=1):
            try:
                chunk = point.payload["chunk"]
                results.append(
                    EvidenceResult(
                        rank=rank,
                        score=point.score,
                        chunk_id=chunk["chunk_id"],
                        text=chunk["text"],
                        review_required=chunk["review_required"],
                        source=EvidenceSource(
                            source_id=chunk["source_id"],
                            source_type=chunk["source_type"],
                            source_path=chunk["source_path"],
                            source_version=chunk["source_version"],
                            location=chunk["location"],
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise IndexUnavailable("Evidence payload is invalid") from error
        response = SearchResponse(
            index_fingerprint=directory.name,
            collection=request.collection,
            query=request.query,
            filters=request.filters,
            results=results,
        )
        LOGGER.info(
            "evidence_search %s",
            json.dumps(
                {
                    "request_id": request_id,
                    "index_fingerprint": directory.name,
                    "collection": request.collection,
                    "filters": request.filters.model_dump(exclude_none=True),
                    "results": len(results),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                sort_keys=True,
            ),
        )
        return response
