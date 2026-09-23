import copy
import json
from pathlib import Path

import pytest


EXPECTED_SOURCE_IDS = [
    "qasper:1601.02166",
    "qasper:1601.06081",
    "qasper:1601.06738",
    "qasper:1602.00812",
    "qasper:1602.03661",
    "qasper:1604.00117",
    "qasper:1604.00125",
    "qasper:1604.05781",
]


def config_payload():
    return json.loads(
        Path("configs/evaluation/p46-quality-v2.json").read_text(encoding="utf-8")
    )


def test_v2_contract_is_frozen():
    from scripts.evaluate_research_cards_v2 import validate_contract

    config = config_payload()
    validated = validate_contract(config, prior_source_ids=set())
    assert [case["source_id"] for case in validated["cases"]] == EXPECTED_SOURCE_IDS
    assert validated["split"] == "train"
    assert validated["model"] == "deepseek-v4-pro"
    assert validated["max_paid_calls"] == 8
    assert validated["retry_limit"] == 0
    assert validated["thresholds"] == {
        "tool_submission_success": 0.875,
        "evidence_support_rate": 0.90,
        "field_classification_accuracy": 0.85,
        "missing_field_identification_rate": 0.85,
    }


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda c: c["cases"].pop(), "exactly eight"),
        (
            lambda c: c["cases"].__setitem__(1, copy.deepcopy(c["cases"][0])),
            "distinct",
        ),
        (lambda c: c.__setitem__("model", "deepseek-flash"), "model"),
        (lambda c: c.__setitem__("max_paid_calls", 9), "call cap"),
        (lambda c: c.__setitem__("retry_limit", 1), "retry"),
    ],
)
def test_v2_contract_rejects_drift(mutate, match):
    from scripts.evaluate_research_cards_v2 import validate_contract

    config = config_payload()
    mutate(config)
    with pytest.raises(ValueError, match=match):
        validate_contract(config, prior_source_ids=set())


def test_v2_contract_normalizes_ids_before_freshness_check():
    from scripts.evaluate_research_cards_v2 import normalize_source_id, validate_contract

    assert normalize_source_id("1601.02166") == "qasper:1601.02166"
    config = config_payload()
    config["cases"][0]["source_id"] = "1601.02166"
    with pytest.raises(ValueError, match="prior runs"):
        validate_contract(config, prior_source_ids={"qasper:1601.02166"})
