from __future__ import annotations

import hashlib
from pathlib import Path

from ican.indexing.inputs import load_chunks
from ican.retrieval.schema import EvidenceResult, EvidenceSource, SearchRequest
from ican.retrieval.scope import eligible, query_config_paths, resolve_family
from ican.retrieval.service import CollectionNotFound

from .schema import ToolInputError


class AgentCorpus:
    def __init__(self, root, index_config, evidence_service, request, rows=None):
        self.root = Path(root)
        self.request = request
        self.service = evidence_service
        dense = getattr(evidence_service, "dense", evidence_service)
        directory, manifest = dense._load_index()
        self.fingerprint = directory.name
        if request.collection not in manifest["collections"]:
            raise CollectionNotFound("Unknown collection")
        if rows is None:
            rows, _ = load_chunks(self.root, index_config)
        self.registry = {
            r["chunk"]["chunk_id"]: r["chunk"]
            for r in rows
            if r["collection"] == request.collection
        }
        self.family, _ = resolve_family(
            request.query, request.collection, request.family
        )
        self.config_paths = query_config_paths(
            list(self.registry.values()), request.query
        )

    def allowed(self, row):
        return eligible(row, self.request, self.family) and (
            row["source_type"] != "config"
            or self.config_paths is None
            or row["source_path"] in self.config_paths
        )

    def evidence(self, cid):
        row = self.registry.get(cid)
        if row is None or not self.allowed(row):
            raise ToolInputError("Evidence ID is absent or outside the task scope")
        return EvidenceResult(
            rank=1,
            score=0,
            chunk_id=cid,
            text=row["text"],
            review_required=row["review_required"],
            source=EvidenceSource(
                **{
                    k: row[k]
                    for k in [
                        "source_id",
                        "source_type",
                        "source_path",
                        "source_version",
                        "location",
                    ]
                }
            ),
        )

    def read(self, chunk_id: str, structure: str, source_path: str):
        if chunk_id:
            return [self.evidence(chunk_id)]
        if not structure or len(structure) > 128:
            raise ToolInputError("Provide a chunk ID or exact structure name")
        rows = [
            r
            for r in self.registry.values()
            if self.allowed(r)
            and r.get("structure_name") == structure
            and (not source_path or r["source_path"] == source_path)
        ]
        rows.sort(key=lambda r: (r["source_path"], r["char_start"], r["chunk_id"]))
        return [self.evidence(r["chunk_id"]) for r in rows[:4]]

    def source_text(self, path: str):
        rows = [
            r
            for r in self.registry.values()
            if r["source_path"] == path and self.allowed(r)
        ]
        if not rows:
            raise ToolInputError("Source file is absent or outside the task scope")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ToolInputError("Source path escapes the project")
        content = target.read_bytes()
        if len(content) > 1_000_000 or any(
            r["source_sha256"] != hashlib.sha256(content).hexdigest() for r in rows
        ):
            raise ToolInputError("Source file identity or size is invalid")
        return content.decode("utf-8-sig")

    def at_line(self, path: str, line: int):
        return [
            self.evidence(r["chunk_id"])
            for r in self.registry.values()
            if r["source_path"] == path
            and self.allowed(r)
            and r["location"].get("line_start", line + 1)
            <= line
            <= r["location"].get("line_end", line - 1)
        ][:2]

    def search_request(self, query: str, source_types: list[str], strategy: str):
        request = SearchRequest.model_validate(
            self.request.model_dump(exclude={"user_overrides"})
        )
        request.query = query
        request.family = self.family
        request.strategy = strategy
        if source_types:
            requested = set(source_types)
            original = request.filters.source_types
            if original is not None:
                requested &= set(original)
            if not requested:
                return None
            request.filters.source_types = sorted(requested)
        return request
