import json

import pytest

from ican.evaluation.research_card import (
    collect_prior_source_ids,
    evidence_identity,
    field_digest,
    raw_card_fields,
    score_quality_review,
    score_raw_draft_review,
    validate_review_binding,
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


def test_raw_card_fields_preserves_duplicates_from_schema_invalid_action():
    fields = [
        {"name": "result", "value": "1", "quote": "1", "evidence_id": "a"},
        {"name": "result", "value": "2", "quote": "2", "evidence_id": "b"},
    ]
    action = {
        "tool_calls": [
            {
                "function": {
                    "name": "submit_research_card",
                    "arguments": json.dumps(
                        {
                            "decision": "include",
                            "reason": "r",
                            "reason_evidence_ids": ["a"],
                            "fields": fields,
                        }
                    ),
                }
            }
        ]
    }
    assert raw_card_fields(action) == fields


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


def test_raw_draft_score_includes_fields_from_failed_tool_submissions():
    review = {
        "cases": {
            "accepted": {
                "expected_present_fields": ["dataset", "metric"],
                "fields": [
                    {
                        "name": "dataset",
                        "evidence_supported": True,
                        "type_correct": True,
                        "correct_type": "dataset",
                    }
                ],
                "omitted_present_fields": ["metric"],
            },
            "schema_failed": {
                "expected_present_fields": ["result"],
                "fields": [
                    {
                        "name": "result",
                        "evidence_supported": False,
                        "type_correct": False,
                        "correct_type": "metric",
                    },
                    {
                        "name": "result",
                        "evidence_supported": True,
                        "type_correct": True,
                        "correct_type": "result",
                    },
                ],
                "omitted_present_fields": [],
            },
        }
    }
    scored = score_raw_draft_review(review, total_cases=2)
    assert scored["evidence_support_rate"]["numerator"] == 2
    assert scored["evidence_support_rate"]["denominator"] == 3
    assert scored["field_classification_accuracy"]["numerator"] == 2
    assert scored["confusions"] == {"result->metric": 1}


def test_review_binds_each_occurrence_not_just_field_names():
    raw = {"a": [{"name": "metric", "value": "F1", "quote": "F1", "evidence_id": "e1"}]}
    review = {
        "cases": {
            "a": {
                "fields": [
                    {
                        "name": "metric",
                        "occurrence": 0,
                        "raw_field_sha256": field_digest(raw["a"][0]),
                        "evidence_supported": True,
                        "type_correct": True,
                        "correct_type": "metric",
                    }
                ]
            }
        }
    }
    validate_review_binding(raw, review)
    raw["a"][0]["value"] = "recall"
    with pytest.raises(ValueError, match="identity"):
        validate_review_binding(raw, review)
    with pytest.raises(ValueError, match="counts"):
        validate_review_binding({"a": []}, review)


def test_sealed_artifact_tampering_is_rejected_before_scoring(tmp_path):
    import hashlib

    from ican.evaluation.research_audit import verify_audit_inputs

    artifact = tmp_path / "manifest.json"
    artifact.write_text("{}", encoding="utf-8")
    seal = {
        "artifact_sha256": {
            "manifest.json": hashlib.sha256(artifact.read_bytes()).hexdigest()
        }
    }
    artifact.write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="Sealed artifact changed"):
        verify_audit_inputs(tmp_path, tmp_path, {}, seal)
