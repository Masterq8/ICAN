import pytest

from ican.research.field_rules import diagnose_field_assignment


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("dataset", "WikiQA benchmark dataset"),
        ("metric", "mean reciprocal rank"),
        ("result", "The model achieves 92.4% accuracy"),
        ("dataset", "SST-2"),
        ("metric", "F1 score"),
    ],
)
def test_valid_dataset_metric_result_assignments_are_not_flagged(name, value):
    assert diagnose_field_assignment(name, value) == []


@pytest.mark.parametrize(
    ("name", "value", "code", "suggested"),
    [
        ("dataset", "F1 score", "dataset_is_metric", "metric"),
        ("dataset", "achieves 92.4% accuracy", "dataset_is_result", "result"),
        ("metric", "evaluated on the WikiQA dataset", "metric_is_dataset", "dataset"),
        (
            "metric",
            "outperforms the baseline by 3.2 points",
            "metric_is_result",
            "result",
        ),
        ("result", "mean reciprocal rank", "result_is_metric", "metric"),
        ("result", "the SST-2 dataset", "result_is_dataset", "dataset"),
    ],
)
def test_strong_cross_type_conflicts_have_actionable_diagnostics(
    name, value, code, suggested
):
    diagnostics = diagnose_field_assignment(name, value)
    assert [item.code for item in diagnostics] == [code]
    assert diagnostics[0].suggested_field == suggested
    assert diagnostics[0].severity == "review"


def test_other_field_types_are_outside_the_deterministic_rule_scope():
    assert diagnose_field_assignment("model", "accuracy") == []
