import pytest

from ican.retrieval.lexical import LexicalIndex, expand_query, fuse, tokens
from ican.retrieval.reranking import RerankerConfig, checked_scores, model_files
from ican.retrieval.schema import SearchRequest
from ican.retrieval.scope import eligible, query_config_paths, resolve_family


def chunk(identifier, path, text, name="", kind="code"):
    return {
        "chunk_id": identifier,
        "source_path": path,
        "text": text,
        "structure_name": name,
        "context_path": [],
        "source_type": kind,
    }


def test_identifiers_and_chinese_are_searchable():
    got = tokens("PatchEmbed.patches_resolution MODEL.DROP_PATH_RATE 学习率")
    assert {
        "patchembed.patches_resolution",
        "patch",
        "embed",
        "drop_path_rate",
        "学习",
    } <= set(got)
    assert "accumulation_steps" in tokens(
        " ".join(expand_query("--accumulation-steps 2"))
    )


def test_exact_config_field_and_file_beat_variant():
    rows = [
        chunk(
            "target",
            "configs/swin/swin_tiny.yaml",
            "DROP_PATH_RATE: 0.2",
            "MODEL.DROP_PATH_RATE",
            "config",
        ),
        chunk(
            "wrong",
            "configs/swinv2/swin_tiny.yaml",
            "DROP_PATH_RATE: 0.1",
            "MODEL.DROP_PATH_RATE",
            "config",
        ),
        chunk("other", "optimizer.py", "weight_decay=0"),
    ]
    result = LexicalIndex(rows).search(
        "configs/swin/swin_tiny.yaml MODEL.DROP_PATH_RATE", {"target", "other"}, 5
    )
    assert result[0][0] == "target"
    assert "wrong" not in {r[0] for r in result}


def test_rrf_counts_each_channel_once_and_has_stable_ties():
    assert fuse([["b", "b", "a"], ["a", "b"]]) == fuse([["b", "a"], ["a", "b"]])
    assert [r[0] for r in fuse([["b"], ["a"]])] == ["a", "b"]


def test_family_override_and_ambiguity():
    assert resolve_family("Swin V2", "swin_v1", "auto")[0] == "swin_v2"
    assert resolve_family("Swin V2与Swin MoE比较", "swin_v1", "auto")[0] == "all"
    assert resolve_family("Swin V2", "swin_v1", "swin_v1")[0] == "swin_v1"
    assert resolve_family("学习率", "swin_v1", "auto")[0] == "swin_v1"
    assert resolve_family("Swin-T与Swin V2比较", "swin_v1", "auto")[0] == "all"


def test_scope_intersection_keeps_shared_entry_but_excludes_simmim():
    request = SearchRequest(
        query="resume",
        collection="swin_v1",
        filters={"source_types": ["code"], "path_prefixes": ["repo/"]},
    )
    assert eligible(chunk("a", "repo/main.py", "resume"), request, "swin_v1")
    assert not eligible(
        chunk("b", "repo/main_simmim_pt.py", "resume"), request, "swin_v1"
    )
    assert not eligible(chunk("c", "other/main.py", "resume"), request, "swin_v1")
    assert not eligible(
        chunk("d", "repo/config.yaml", "resume", kind="config"), request, "swin_v1"
    )


@pytest.mark.parametrize("values", [[float("nan")], [float("inf")], [1.0, 2.0]])
def test_bad_reranker_outputs_fail_closed(values):
    with pytest.raises(ValueError, match="finite logit"):
        checked_scores(values, 1)


def service_rows():
    rows = []
    for cid, path, text, name in [
        (
            "header",
            "repo/models/swin_transformer.py",
            "class PatchEmbed:",
            "PatchEmbed",
        ),
        (
            "init",
            "repo/models/swin_transformer.py",
            "self.proj=Conv2d(kernel_size=4)",
            "PatchEmbed.__init__",
        ),
        (
            "forward",
            "repo/models/swin_transformer.py",
            "x.flatten(2).transpose(1,2)",
            "PatchEmbed.forward",
        ),
        (
            "variant",
            "repo/models/swin_transformer_v2.py",
            "PatchEmbed Conv2d",
            "PatchEmbed.__init__",
        ),
    ]:
        c = chunk(cid, path, text, name)
        c.update(
            source_id=cid,
            source_version="fixed",
            review_required=False,
            location={"line_start": 1, "line_end": 2},
            char_start=len(rows) * 20,
            structure_kind="class" if cid == "header" else "method",
        )
        rows.append({"id": cid, "collection": "swin_v1", "chunk": c})
    return rows


class FakeDense:
    def __init__(self, rows, leak=False):
        self.rows, self.leak = rows, leak
        self.calls = 0

    def _load_index(self):
        from pathlib import Path

        return Path("fake-index"), {"collections": {"swin_v1": len(self.rows)}}

    def candidates(self, request, limit, allowed_point_ids):
        from types import SimpleNamespace

        self.calls += 1
        return SimpleNamespace(
            results=[
                SimpleNamespace(chunk_id=r["chunk"]["chunk_id"], score=0.9)
                for r in self.rows
                if self.leak or r["id"] in allowed_point_ids
            ]
        )


class FakeReranker:
    def __init__(self):
        self.descriptor = {"repository": "offline", "revision": "fixed"}

    def score(self, query, passages):
        return list(range(len(passages), 0, -1)), {"truncated_pairs": 0}


def test_real_wrapper_enforces_filters_and_preserves_original_context_chunks():
    from pathlib import Path

    from ican.retrieval.hybrid import HybridEvidenceSearchService
    from ican.retrieval.policy import RetrievalPolicy

    rows = service_rows()
    service = HybridEvidenceSearchService(
        Path("."),
        None,
        rows=rows,
        dense_service=FakeDense(rows),
        policy=RetrievalPolicy(),
        reranker=FakeReranker(),
    )
    response = service.search(
        SearchRequest(
            query="PatchEmbed",
            collection="swin_v1",
            strategy="hybrid_rerank",
            limit=3,
            filters={"path_prefixes": ["repo/models/swin_transformer.py"]},
        )
    )
    assert {c.chunk_id for c in response.results} == {"header", "init", "forward"}
    assert all(
        c.source.source_path == "repo/models/swin_transformer.py"
        for c in response.results
    )
    assert response.trace["family"] == "swin_v1"
    original = {r["chunk"]["chunk_id"]: r["chunk"] for r in rows}
    assert all(c.text == original[c.chunk_id]["text"] for c in response.results)


def test_leaky_dense_injection_is_rejected_not_silently_filtered():
    from pathlib import Path

    from ican.retrieval.hybrid import HybridEvidenceSearchService
    from ican.retrieval.policy import RetrievalPolicy
    from ican.retrieval.service import IndexUnavailable

    rows = service_rows()
    service = HybridEvidenceSearchService(
        Path("."),
        None,
        rows=rows,
        dense_service=FakeDense(rows, leak=True),
        policy=RetrievalPolicy(),
    )
    with pytest.raises(IndexUnavailable):
        service.search(
            SearchRequest(query="PatchEmbed", collection="swin_v1", strategy="hybrid")
        )


def test_unknown_collection_and_bm25_do_not_load_models():
    from pathlib import Path

    from ican.retrieval.hybrid import HybridEvidenceSearchService
    from ican.retrieval.policy import RetrievalPolicy
    from ican.retrieval.service import CollectionNotFound

    rows = service_rows()
    dense = FakeDense(rows)
    service = HybridEvidenceSearchService(
        Path("."), None, rows=rows, dense_service=dense, policy=RetrievalPolicy()
    )
    with pytest.raises(CollectionNotFound):
        service.search(
            SearchRequest(query="x", collection="unknown", strategy="hybrid_rerank")
        )
    service.search(
        SearchRequest(query="PatchEmbed", collection="swin_v1", strategy="bm25")
    )
    assert dense.calls == 0 and service.reranker is None


@pytest.mark.parametrize(
    ("strategy", "meaning"),
    [
        ("dense_scoped", "cosine"),
        ("bm25", "bm25_positive_idf"),
        ("hybrid", "reciprocal_rank_fusion"),
        ("hybrid_rerank", "reranker_uncalibrated_logit"),
        ("dense", "cosine"),
    ],
)
def test_wrapper_explicit_family_and_score_trace(strategy, meaning):
    from pathlib import Path

    from ican.retrieval.hybrid import HybridEvidenceSearchService
    from ican.retrieval.policy import RetrievalPolicy

    rows = service_rows()
    service = HybridEvidenceSearchService(
        Path("."),
        None,
        rows=rows,
        dense_service=FakeDense(rows),
        policy=RetrievalPolicy(),
        reranker=FakeReranker(),
    )
    response = service.search(
        SearchRequest(
            query="PatchEmbed",
            collection="swin_v1",
            strategy=strategy,
            family="swin_v2",
            filters={"source_types": ["code"]},
        )
    )
    assert [r.chunk_id for r in response.results] == ["variant"]
    assert response.trace["family"] == "swin_v2"
    assert response.trace["score_meaning"] == meaning
    assert response.trace["context_added_chunk_ids"] == []


def test_empty_scope_does_not_load_reranker():
    from pathlib import Path

    from ican.retrieval.hybrid import HybridEvidenceSearchService
    from ican.retrieval.policy import RetrievalPolicy

    rows = service_rows()
    service = HybridEvidenceSearchService(
        Path("."),
        None,
        rows=rows,
        dense_service=FakeDense(rows),
        policy=RetrievalPolicy(),
    )
    response = service.search(
        SearchRequest(
            query="PatchEmbed",
            collection="swin_v1",
            strategy="hybrid_rerank",
            filters={"source_types": ["paper"]},
        )
    )
    assert response.results == []
    assert service.reranker is None


def test_named_yaml_scope_follows_existing_base_references_and_cycles_only():
    rows = [
        chunk(
            "child", "configs/swin/child.yaml", "BASE: ['base.yaml']", "BASE", "config"
        ),
        chunk(
            "parent",
            "configs/swin/base.yaml",
            "BASE: ['child.yaml', '../../unknown.yaml']",
            "BASE",
            "config",
        ),
        chunk(
            "other",
            "configs/swin/other.yaml",
            "DROP_PATH_RATE: 0.2",
            "MODEL.DROP_PATH_RATE",
            "config",
        ),
    ]
    assert query_config_paths(rows, "使用child.yaml的配置链") == {
        "configs/swin/child.yaml",
        "configs/swin/base.yaml",
    }
    assert query_config_paths(rows, "missing.yaml") == set()
    assert query_config_paths(rows, "默认配置") is None


def test_model_size_scope_preserves_shared_code_and_comparison():
    tiny = chunk("t", "configs/swin/swin_tiny_patch4.yaml", "value", kind="config")
    base = chunk("b", "configs/swin/swin_base_patch4.yaml", "value", kind="config")
    request = SearchRequest(query="Swin-T的配置", collection="swin_v1")
    assert eligible(tiny, request, "swin_v1")
    assert not eligible(base, request, "swin_v1")
    assert eligible(chunk("code", "config.py", "defaults"), request, "swin_v1")
    comparison = request.model_copy(update={"query": "Swin-T与Swin-B的配置比较"})
    assert eligible(tiny, comparison, "swin_v1") and eligible(
        base, comparison, "swin_v1"
    )


def test_configuration_chain_adds_original_defaults_and_merge_functions():
    from ican.retrieval.hybrid import structural_selection

    rows = {
        "value": chunk(
            "value",
            "configs/swin/target.yaml",
            "DROP_PATH_RATE: 0.2",
            "MODEL.DROP_PATH_RATE",
            "config",
        ),
        "defaults": chunk("defaults", "config.py", "_C.MODEL.DROP_PATH_RATE = 0.1"),
        "file": chunk(
            "file",
            "config.py",
            "config.merge_from_file(cfg_file)",
            "_update_config_from_file",
        ),
        "opts": chunk(
            "opts", "config.py", "config.merge_from_list(args.opts)", "update_config"
        ),
        "wrong": chunk("wrong", "config_simmim.py", "_C.MODEL.DROP_PATH_RATE = 0.5"),
    }
    for i, row in enumerate(rows.values()):
        row["char_start"] = i
    allowed = set(rows) - {"wrong"}
    selected, extra = structural_selection(
        ["value"],
        rows,
        allowed,
        "使用target.yaml的配置链，MODEL.DROP_PATH_RATE被覆盖；update_config merge_from_list",
        4,
        3,
    )
    assert set(selected) == allowed
    assert set(extra) == {"defaults", "file", "opts"}


def test_named_yaml_field_is_preserved_when_reranker_omits_it():
    from ican.retrieval.hybrid import structural_selection

    rows = {
        str(i): chunk(str(i), "README.md", "documentation", kind="documentation")
        for i in range(8)
    }
    rows["field"] = chunk(
        "field",
        "configs/swin/target.yaml",
        "DROP_PATH_RATE: 0.2",
        "MODEL.DROP_PATH_RATE",
        "config",
    )
    for i, row in enumerate(rows.values()):
        row["char_start"] = i
    selected, extra = structural_selection(
        list(rows)[:8],
        rows,
        set(rows),
        "target.yaml的MODEL.DROP_PATH_RATE配置链",
        8,
        3,
    )
    assert "field" in selected and extra == ["field"]
    assert len(selected) == 8


@pytest.mark.parametrize("suffix", ["foo", "_foo", "1foo"])
def test_yaml_field_anchor_does_not_match_identifier_prefix(suffix):
    from ican.retrieval.hybrid import structural_selection

    rows = {
        str(i): chunk(str(i), "README.md", "documentation", kind="documentation")
        for i in range(3)
    }
    rows["field"] = chunk(
        "field",
        "configs/swin/target.yaml",
        "DROP_PATH_RATE: 0.2",
        "MODEL.DROP_PATH_RATE",
        "config",
    )
    selected, extra = structural_selection(
        ["0", "1", "2"],
        rows,
        set(rows),
        f"target.yaml的配置链，MODEL.DROP_PATH_RATE{suffix}是什么？",
        3,
        1,
    )
    assert selected == ["0", "1", "2"]
    assert not extra


@pytest.mark.parametrize("mutation", ["missing", "sha", "extra", "escape"])
def test_reranker_snapshot_rejects_missing_changed_unverified_or_outside_files(
    tmp_path, mutation
):
    import hashlib

    directory = tmp_path / "data/cache/reranking/model"
    directory.mkdir(parents=True)
    path = directory / "model.safetensors"
    path.write_bytes(b"original")
    config = RerankerConfig(
        repository="BAAI/bge-reranker-v2-m3",
        revision="a" * 40,
        local_path="data/cache/reranking/model",
        ledger_path="data/catalog/model.json",
        files={
            "model.safetensors": {
                "size": 8,
                "sha256": hashlib.sha256(b"original").hexdigest(),
            }
        },
    )
    assert model_files(tmp_path, config)["model.safetensors"]["bytes"] == 8
    if mutation == "missing":
        path.unlink()
    elif mutation == "sha":
        path.write_bytes(b"modified")
    elif mutation == "extra":
        (directory / "unverified.json").write_bytes(b"{}")
    else:
        config = config.model_copy(
            update={"files": {"../../../../outside": next(iter(config.files.values()))}}
        )
    with pytest.raises(ValueError):
        model_files(tmp_path, config)
