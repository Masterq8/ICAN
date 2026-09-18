from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock

from ican.indexing.inputs import load_chunks
from ican.indexing.schema import IndexConfig
from ican.ingestion.pipeline import confined

from .lexical import LexicalIndex, expand_query, fuse, tokens
from .policy import RetrievalPolicy
from .reranking import LocalReranker, RerankerConfig, checked_scores
from .schema import EvidenceResult, EvidenceSource, SearchRequest, SearchResponse
from .scope import eligible, query_config_paths, resolve_family
from .service import CollectionNotFound, EvidenceSearchService, IndexUnavailable


def structural_selection(
    ordered: list[str],
    registry: dict,
    allowed: set[str],
    query: str,
    limit: int,
    additions: int,
) -> tuple[list[str], list[str]]:
    """Add existing named structures/configuration anchors within the evidence budget."""
    if not additions or limit < 3:
        return ordered[:limit], []
    selected = ordered[:limit]
    protected = set(selected[: min(3, max(1, limit - additions))])
    extra = []
    terms = set(tokens(query))
    # Use explicit entities and narrowly defined terminology, not broad merge aliases.
    if "linear embedding" in query.lower():
        terms.add("patchembed")
    if "--accumulation-steps" in query or "梯度累积" in query:
        terms.add("train_one_epoch")
    anchors = []
    config_chain = bool(
        query_config_paths([registry[cid] for cid in allowed], query)
    ) and ("配置" in query or "--opts" in query or "override" in query.lower())
    fields = set(
        re.findall(
            r"(?<![a-zA-Z0-9_])[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+(?![a-zA-Z0-9_])",
            query,
        )
    )
    for cid in allowed:
        row = registry[cid]
        if (
            config_chain
            and row["source_type"] == "config"
            and row.get("structure_name") in fields
        ):
            anchors.append((cid, 0, row["source_path"], row["char_start"]))
            continue
        if row["source_type"] != "code":
            continue
        name = row.get("structure_name", "")
        entity = name.split(".")[0]
        if entity and entity.lower() in terms:
            member = name.split(".")[-1]
            if (
                "." in name
                and member not in {"__init__", "forward"}
                and name.lower() not in terms
            ):
                continue
            priority = (
                2
                if row.get("structure_kind") == "class"
                else (1 if member == "forward" else 0)
            )
            anchors.append((cid, priority, row["source_path"], row["char_start"]))
        elif config_chain and (
            any("_C." + field in row["text"] for field in fields)
            or name in {"_update_config_from_file", "update_config"}
        ):
            priority = 0 if any("_C." + field in row["text"] for field in fields) else 1
            anchors.append((cid, priority, row["source_path"], row["char_start"]))
    for cid, priority, _, _ in sorted(anchors, key=lambda r: (r[1], r[2], r[3], r[0])):
        if cid in selected or len(extra) >= additions:
            continue
        if len(selected) >= limit:
            replaceable = [
                old for old in selected if old not in protected and old not in extra
            ]
            redundant_docs = [
                old
                for old in replaceable
                if registry[old]["source_type"] == "documentation"
                and sum(
                    registry[item]["source_path"] == registry[old]["source_path"]
                    for item in selected
                )
                > 1
            ]
            choices = redundant_docs or (replaceable if priority < 2 else [])
            if not choices:
                continue
            selected.remove(choices[-1])
        selected.append(cid)
        extra.append(cid)
    return selected, extra


class HybridEvidenceSearchService:
    """Opt-in retrieval strategies over the same verified immutable evidence."""

    def __init__(
        self,
        root: Path,
        config: IndexConfig,
        *,
        dense_service=None,
        rows=None,
        policy: RetrievalPolicy | None = None,
        reranker=None,
    ):
        self.root = root.resolve()
        self.config = config
        self.dense = dense_service or EvidenceSearchService(root, config)
        self.policy = policy or RetrievalPolicy.model_validate_json(
            (root / "configs/retrieval/v1.json").read_text(encoding="utf-8")
        )
        self.rows = rows  # Explicitly unverified test seam, never used by production.
        self.lexical = {}
        self.registry = {}
        self.point_ids = {}
        self.reranker = reranker
        self._corpus_lock = Lock()
        self._reranker_lock = Lock()
        self._corpus_ready = False

    def _ensure_corpus(self):
        directory, manifest = self.dense._load_index()
        with self._corpus_lock:
            if not self._corpus_ready:
                if self.rows is None:
                    self.rows, _ = load_chunks(self.root, self.config)
                grouped = defaultdict(list)
                for row in self.rows:
                    chunk = row["chunk"]
                    grouped[row["collection"]].append(chunk)
                    self.registry[chunk["chunk_id"]] = chunk
                    self.point_ids[chunk["chunk_id"]] = row["id"]
                if set(grouped) != set(manifest["collections"]):
                    raise ValueError("Lexical collection set differs from dense index")
                self.lexical = {
                    name: LexicalIndex(chunks, self.policy.bm25_k1, self.policy.bm25_b)
                    for name, chunks in grouped.items()
                }
                identity = [
                    {
                        "collection": r["collection"],
                        "chunk_id": r["chunk"]["chunk_id"],
                        "text": r["chunk"]["text"],
                        "path": r["chunk"]["source_path"],
                        "name": r["chunk"].get("structure_name", ""),
                        "context": r["chunk"].get("context_path", []),
                    }
                    for r in self.rows
                ]
                self.lexical_fingerprint = hashlib.sha256(
                    json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                self._corpus_ready = True
        return directory, manifest

    def _reranker(self):
        with self._reranker_lock:
            if self.reranker is None:
                path = confined(self.root, self.policy.reranker_config, "configs")
                cfg = RerankerConfig.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                self.reranker = LocalReranker(self.root, cfg)
        return self.reranker

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.strategy == "dense":
            if request.family in {"auto", "all"}:
                return self.dense.search(request)
            # Explicit family constraints must also be honored by dense requests.
            request = request.model_copy(update={"strategy": "dense_scoped"})
        started = time.perf_counter()
        try:
            directory, manifest = self._ensure_corpus()
            if request.collection not in manifest["collections"]:
                raise CollectionNotFound("Unknown evidence collection")
            family, reason = resolve_family(
                request.query, request.collection, request.family
            )
            config_paths = query_config_paths(
                self.lexical[request.collection].rows, request.query
            )
            allowed = {
                c["chunk_id"]
                for c in self.lexical[request.collection].rows
                if eligible(c, request, family)
                and (
                    config_paths is None
                    or c["source_type"] != "config"
                    or c["source_path"] in config_paths
                )
            }
            expanded = expand_query(request.query)
            lexical_query = request.query + " " + " ".join(expanded)
            dense_hits = []
            lexical_hits = []
            if request.strategy != "bm25":
                response = self.dense.candidates(
                    request,
                    self.policy.candidate_limit,
                    [self.point_ids[cid] for cid in sorted(allowed)],
                )
                dense_hits = [(r.chunk_id, r.score) for r in response.results]
                if any(cid not in allowed for cid, _ in dense_hits):
                    raise ValueError("Dense candidates violated requested scope")
            if request.strategy != "dense_scoped":
                lexical_hits = self.lexical[request.collection].search(
                    lexical_query, allowed, self.policy.candidate_limit
                )
            if request.strategy == "bm25":
                ranked, meaning = lexical_hits, "bm25_positive_idf"
            elif request.strategy == "dense_scoped":
                ranked, meaning = dense_hits, "cosine"
            else:
                ranked = fuse(
                    [[cid for cid, _ in dense_hits], [cid for cid, _ in lexical_hits]],
                    self.policy.rrf_k,
                )
                meaning = "reciprocal_rank_fusion"
            reranking = {}
            reranker_identity = None
            if request.strategy == "hybrid_rerank" and ranked:
                pool = ranked[: self.policy.rerank_limit]
                ranker = self._reranker()
                passages = [
                    self.registry[cid].get("embedding_context", "")
                    + "\n"
                    + self.registry[cid].get("structure_name", "")
                    + "\n"
                    + self.registry[cid]["text"]
                    for cid, _ in pool
                ]
                scores, reranking = ranker.score(request.query, passages)
                scores = checked_scores(scores, len(pool))
                ranked = sorted(
                    [(cid, s) for (cid, _), s in zip(pool, scores, strict=True)],
                    key=lambda r: (-r[1], r[0]),
                )
                meaning = "reranker_uncalibrated_logit"
                reranker_identity = ranker.descriptor
            ordered = [cid for cid, _ in ranked]
            selected, extra = structural_selection(
                ordered,
                self.registry,
                allowed,
                request.query,
                request.limit,
                self.policy.max_context_additions
                if self.policy.structural_context
                and request.strategy == "hybrid_rerank"
                else 0,
            )
            score_map = dict(ranked)
            results = []
            for rank, cid in enumerate(selected, start=1):
                c = self.registry[cid]
                results.append(
                    EvidenceResult(
                        rank=rank,
                        score=score_map.get(cid, 0.0),
                        chunk_id=cid,
                        text=c["text"],
                        review_required=c["review_required"],
                        source=EvidenceSource(
                            **{
                                k: c[k]
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
                )
            return SearchResponse(
                index_fingerprint=directory.name,
                collection=request.collection,
                query=request.query,
                filters=request.filters,
                results=results,
                trace={
                    "strategy": request.strategy,
                    "family": family,
                    "family_reason": reason,
                    "expanded_terms": expanded,
                    "query_config_paths": sorted(config_paths)
                    if config_paths is not None
                    else None,
                    "lexical_fingerprint": self.lexical_fingerprint,
                    "policy": self.policy.model_dump(),
                    "eligible_n": len(allowed),
                    "dense_candidates": dense_hits,
                    "bm25_candidates": lexical_hits,
                    "ranked_candidates": ranked,
                    "score_meaning": meaning,
                    "context_added_chunk_ids": extra,
                    "context_score_note": "unranked siblings have placeholder0; not relevance scores",
                    "reranker": reranker_identity,
                    "reranking": reranking,
                    "elapsed_seconds": time.perf_counter() - started,
                },
            )
        except CollectionNotFound:
            raise
        except IndexUnavailable:
            raise
        except Exception as error:
            raise IndexUnavailable("Hybrid evidence retrieval failed") from error
