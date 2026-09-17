import copy

import pytest

from scripts.finalize_baseline_audit import (
    finalize,
    validate_completed_run,
    validate_reviews,
)


def review():
    return {
        "case_key": "swin/dev/example",
        "variant": "adapter",
        "answer_judgment": "partial",
        "grading_point_scores": [1, 0],
        "reason": "Missing runtime scaling formula",
        "citation_support": "partial",
        "citation_reason": "Only YAML value cited",
        "semantic_abstained": False,
        "semantic_status_correct": None,
    }


def test_same_answer_cannot_be_reviewed_twice_to_hide_missing_case():
    row = review()
    completed = {"swin/dev/example/adapter": {}, "swin/dev/example/paperqa-default": {}}
    with pytest.raises(ValueError, match="exactly once"):
        validate_reviews([row, copy.deepcopy(row)], completed, {})


def test_grading_points_cannot_be_added_or_dropped():
    row = review()
    row["grading_point_scores"] = [1]
    with pytest.raises(ValueError, match="fixed rubric"):
        validate_reviews(
            [row],
            {"swin/dev/example/adapter": {}},
            {row["case_key"]: {"grading_points": ["value", "chain"]}},
        )


def test_audit_cannot_be_replayed_against_another_generation(tmp_path):
    directory = tmp_path / "run"
    review_directory = tmp_path / "reviews"
    directory.mkdir()
    review_directory.mkdir()
    (directory / "journal.jsonl").write_text("new generation", encoding="utf-8")
    (review_directory / "p26-audit-manifest.json").write_text(
        '{"journal_sha256":"previous generation hash"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="different generation journal"):
        finalize(tmp_path, directory, review_directory)


@pytest.mark.parametrize(
    "corruption", ["duplicate_start", "duplicate_completion", "extra_call"]
)
def test_journal_integrity_does_not_hide_duplicate_or_multiple_calls(corruption):
    journal = [
        {"event": "started", "key": "a"},
        {"event": "completed", "key": "a", "usage": {"generation_calls": 1}},
        {"event": "started", "key": "b"},
        {"event": "completed", "key": "b", "usage": {"generation_calls": 1}},
    ]
    if corruption == "duplicate_start":
        journal[2]["key"] = "a"  # Same count, but b's own reservation is missing.
    elif corruption == "duplicate_completion":
        journal.append(copy.deepcopy(journal[1]))
    else:
        journal[1]["usage"]["generation_calls"] = 2
    with pytest.raises(ValueError, match="unique paired starts"):
        validate_completed_run(journal, {"a", "b"})
