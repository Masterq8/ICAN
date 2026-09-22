import json

import pytest

from ican.evaluation.research_card import (
    collect_prior_source_ids,
    evidence_identity,
    score_quality_review,
)
from ican.retrieval.schema import EvidenceResult, EvidenceSource


def evidence(chunk_id="c1", text="Evaluated on WikiQA with MRR."):
    return EvidenceResult(
        rank=1,
        score=0.9,
        chunk_id=chunk_id,
        text=text,
        review_required=False,
        source=EvidenceSource(
            source_id="qasper:paper-a",
            source_type="paper",
            source_path="qasper/paper-a",
            source_version="v1",
            location={"section_index": 2, "paragraph_index": 1},
        ),
    )


def test_evidence_identity_is_reproducible_and_text_sensitive():
    first = evidence_identity(evidence())
    assert first == evidence_identity(evidence())
    assert (
        first["text_sha256"]
        != evidence_identity(evidence(text="changed"))["text_sha256"]
    )
    assert "text" not in first
    assert first["source_version"] == "v1"


def test_collect_prior_source_ids_reads_nested_json_and_jsonl(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps({"request": {"source_id": "qasper:used-a"}}), encoding="utf-8"
    )
    (tmp_path / "b.jsonl").write_text(
        json.dumps({"source_id": "qasper:used-b"}) + "\n", encoding="utf-8"
    )
    assert collect_prior_source_ids([tmp_path]) == {
        "qasper:used-a",
        "qasper:used-b",
    }


def test_score_quality_keeps_failed_cases_out_of_field_denominators():
    cases = {
        "a": {
            "tool_success": True,
            "submitted_fields": ["dataset", "metric", "result"],
        },
        "b": {"tool_success": False, "submitted_fields": []},
    }
    review = {
        "cases": {
            "a": {
                "expected_present_fields": ["dataset", "metric", "model"],
                "fields": [
                    {
                        "name": "dataset",
                        "evidence_supported": True,
                        "type_correct": True,
                        "correct_type": "dataset",
                    },
                    {
                        "name": "metric",
                        "evidence_supported": True,
                        "type_correct": True,
                        "correct_type": "metric",
                    },
                    {
                        "name": "result",
                        "evidence_supported": False,
                        "type_correct": False,
                        "correct_type": "metric",
                    },
                ],
                "omitted_present_fields": ["model"],
            },
            "b": {
                "expected_present_fields": ["task"],
                "fields": [],
                "omitted_present_fields": [],
            },
        }
    }
    scored = score_quality_review(cases, review, total_cases=2)
    assert scored["tool_submission_success"] == {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
    }
    assert scored["evidence_support_rate"]["rate"] == pytest.approx(2 / 3)
    assert scored["field_classification_accuracy"]["rate"] == pytest.approx(2 / 3)
    # Gold-absent fields are six slots; result was incorrectly filled, so five are omitted.
    assert scored["missing_field_identification_rate"] == {
        "numerator": 5,
        "denominator": 6,
        "rate": pytest.approx(5 / 6),
    }
    assert scored["present_field_recall"] == {
        "numerator": 2,
        "denominator": 3,
        "rate": pytest.approx(2 / 3),
    }
    assert scored["confusions"] == {"result->metric": 1}


def test_review_must_cover_each_successful_submitted_field():
    cases = {"a": {"tool_success": True, "submitted_fields": ["dataset"]}}
    review = {
        "cases": {
            "a": {
                "expected_present_fields": ["dataset"],
                "fields": [],
                "omitted_present_fields": [],
            }
        }
    }
    with pytest.raises(ValueError, match="reviewed fields"):
        score_quality_review(cases, review, total_cases=1)
