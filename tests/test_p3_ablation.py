from copy import deepcopy

import pytest

from ican.evaluation.data import Case
from ican.retrieval.schema import EvidenceResult, SearchResponse
from scripts.evaluate_retrieval_strategies import raw_ranked_response, validate_records


def fixture():
    case = Case("example", "swin", "dev", "PatchEmbed", "swin_v1", {})
    c = {
        "chunk_id": "a",
        "text": "class PatchEmbed",
        "source_id": "source",
        "source_type": "code",
        "source_path": "models/swin_transformer.py",
        "source_version": "commit",
        "location": {"line_start": 1, "line_end": 1},
        "review_required": False,
    }
    source = {
        k: c[k]
        for k in (
            "source_id",
            "source_type",
            "source_path",
            "source_version",
            "location",
        )
    }
    response = SearchResponse(
        query=case.question,
        collection=case.collection,
        index_fingerprint="fixed",
        filters={},
        results=[
            EvidenceResult(
                rank=1,
                score=2,
                chunk_id="a",
                text=c["text"],
                review_required=False,
                source=source,
            )
        ],
        trace={"ranked_candidates": [["a", 2]], "context_added_chunk_ids": ["a"]},
    )
    row = {
        "key": case.key + "/hybrid_rerank",
        "case_key": case.key,
        "case": case.record(),
        "strategy": "hybrid_rerank",
        "request": {**case.request(), "strategy": "hybrid_rerank"},
        "response": response.model_dump(),
    }
    return case, c, response, row


def test_raw_ablation_preserves_evidence_without_model_dispatch():
    _, c, response, _ = fixture()
    raw = raw_ranked_response(response, {"a": c}, 8)
    assert raw.results == response.results
    assert raw.trace["context_added_chunk_ids"] == []
    assert response.trace["context_added_chunk_ids"] == ["a"]


def test_resume_manifest_rejects_another_index_even_with_no_mixed_records():
    case, c, _, row = fixture()
    with pytest.raises(ValueError, match="immutable manifest"):
        validate_records([row], [case], {"a": c}, "different")


@pytest.mark.parametrize("change", ["duplicate", "text", "variant", "request", "index"])
def test_resume_validation_rejects_changed_or_mixed_results(change):
    case, c, _, row = fixture()
    rows = [row]
    registry = {"a": c}
    validate_records(rows, [case], registry)
    if change == "duplicate":
        rows.append(deepcopy(row))
    elif change == "text":
        row["response"]["results"][0]["text"] = "modified"
    elif change == "variant":
        c["source_path"] = "models/swin_transformer_v2.py"
        row["response"]["results"][0]["source"]["source_path"] = c["source_path"]
    elif change == "request":
        row["request"]["query"] = "gold-derived query"
    else:
        another = deepcopy(row)
        another["strategy"] = "hybrid"
        another["key"] = case.key + "/hybrid"
        another["request"]["strategy"] = "hybrid"
        another["response"]["index_fingerprint"] = "changed"
        rows.append(another)
    with pytest.raises(ValueError):
        validate_records(rows, [case], registry)
