import copy
import asyncio
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


def frozen_payload():
    return {
        "cases": [
            {
                "key": f"paper_{index}",
                "request": {
                    "query": "q",
                    "collection": "qasper_train_v1",
                    "source_id": source_id,
                },
                "evidence": [],
            }
            for index, source_id in enumerate(EXPECTED_SOURCE_IDS, start=1)
        ]
    }


def test_execute_cases_calls_each_source_once_and_never_retries(tmp_path):
    from scripts.evaluate_research_cards_v2 import execute_cases

    calls = []

    async def fake_executor(case):
        calls.append(case["request"]["source_id"])
        if case["key"] == "paper_4":
            return {
                "status": "failed",
                "error_category": "provider_payload",
                "error_type": "FakeProviderError",
                "error": "bad response",
                "raw_action": None,
                "trace": None,
                "usage": None,
                "response_id": None,
                "tool_diagnosis": {"status": "rejected", "code": "runtime_error", "issues": []},
            }
        return {
            "status": "completed",
            "raw_action": {"tool_calls": []},
            "trace": f"{case['key']}.json",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "response_id": f"response-{case['key']}",
            "tool_diagnosis": {"status": "accepted", "code": "accepted", "issues": []},
        }

    config = {"model": "deepseek-v4-pro", "max_paid_calls": 8}
    asyncio.run(execute_cases(config, frozen_payload(), fake_executor, tmp_path))
    asyncio.run(execute_cases(config, frozen_payload(), fake_executor, tmp_path))
    assert calls == EXPECTED_SOURCE_IDS
    results = sorted((tmp_path / "case-results").glob("*.json"))
    assert len(results) == 8
    assert sum(json.loads(path.read_text())["status"] == "completed" for path in results) == 7
    events = [json.loads(line) for line in (tmp_path / "call-journal.jsonl").read_text().splitlines()]
    assert sum(row["event"] == "started" for row in events) == 8
    assert all(row["model"] == "deepseek-v4-pro" for row in events)


def test_started_case_becomes_interrupted_unknown_without_new_call(tmp_path):
    from scripts.evaluate_research_cards_v2 import append_event, execute_cases, request_digest

    payload = frozen_payload()
    first = payload["cases"][0]
    append_event(
        tmp_path / "call-journal.jsonl",
        {
            "event": "started",
            "source_id": first["request"]["source_id"],
            "request_sha256": request_digest(first["request"]),
            "model": "deepseek-v4-pro",
        },
    )
    calls = []

    async def fake_executor(case):
        calls.append(case["request"]["source_id"])
        return {
            "status": "completed",
            "raw_action": None,
            "trace": None,
            "usage": {},
            "response_id": None,
            "tool_diagnosis": {"status": "accepted", "code": "accepted", "issues": []},
        }

    asyncio.run(
        execute_cases(
            {"model": "deepseek-v4-pro", "max_paid_calls": 8},
            payload,
            fake_executor,
            tmp_path,
        )
    )
    assert calls == EXPECTED_SOURCE_IDS[1:]
    first_result = json.loads(
        (tmp_path / "case-results/paper_1.json").read_text(encoding="utf-8")
    )
    assert first_result["status"] == "interrupted_unknown"


def test_preflight_records_model_compatibility_without_secret(tmp_path, monkeypatch):
    import httpx
    import scripts.evaluate_research_cards_v2 as evaluator

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"object": "list", "data": [{"id": "deepseek-v4-pro"}]}

    monkeypatch.setenv("ICAN_LLM_API_KEY", "secret-test-key")
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(evaluator, "PREFLIGHT_PATH", tmp_path / "preflight.json")
    monkeypatch.setattr(evaluator, "source_commit", lambda: "abc123")
    monkeypatch.setattr(evaluator, "collect_prior_source_ids", lambda roots: set())
    record = evaluator.preflight(Path("configs/evaluation/p46-quality-v2.json"))
    serialized = json.dumps(record)
    assert record["status"] == "passed"
    assert record["generation_calls"] == 0
    assert "secret-test-key" not in serialized
