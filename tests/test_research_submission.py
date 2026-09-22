from __future__ import annotations

import json

import pytest

from ican.research.submission import diagnose_card_submission

ALLOWED = {"e1", "e2"}
VALID = {
    "decision": "hold",
    "reason": "The evidence needs review.",
    "reason_evidence_ids": ["e1"],
    "fields": [
        {
            "name": "dataset",
            "value": "WikiQA",
            "quote": "evaluated on WikiQA",
            "evidence_id": "e2",
        }
    ],
}


def action(arguments=None, *, name="submit_research_card", calls=1):
    arguments = json.dumps(VALID) if arguments is None else arguments
    call = {"function": {"name": name, "arguments": arguments}}
    return {"role": "assistant", "tool_calls": [call] * calls}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"role": "assistant"}, "no_tool_call"),
        (action(calls=2), "multiple_tool_calls"),
        ({"tool_calls": [{}]}, "malformed_tool_call"),
        (action(name="other"), "wrong_tool_name"),
        (action(arguments={}), "arguments_not_string"),
        (action(arguments="{"), "invalid_json"),
        (action(arguments=json.dumps({"decision": "hold"})), "schema_invalid"),
    ],
)
def test_submission_failures_have_stable_specific_codes(payload, code):
    diagnosis = diagnose_card_submission(payload, ALLOWED)
    assert diagnosis.status == "rejected"
    assert diagnosis.code == code
    assert diagnosis.draft is None
    assert diagnosis.issues


def test_schema_diagnostic_preserves_field_path_without_raw_secrets():
    diagnosis = diagnose_card_submission(
        action(arguments=json.dumps({"decision": "hold"})), ALLOWED
    )
    paths = {tuple(issue.path) for issue in diagnosis.issues}
    assert ("reason",) in paths
    assert ("fields",) in paths


def test_unknown_evidence_is_distinct_from_protocol_failure():
    payload = dict(VALID)
    payload["fields"] = [dict(VALID["fields"][0], evidence_id="outside")]
    diagnosis = diagnose_card_submission(action(json.dumps(payload)), ALLOWED)
    assert diagnosis.code == "evidence_out_of_scope"
    assert diagnosis.unknown_evidence_ids == ["outside"]


def test_valid_submission_returns_typed_draft():
    diagnosis = diagnose_card_submission(action(), ALLOWED)
    assert diagnosis.status == "accepted"
    assert diagnosis.code == "accepted"
    assert diagnosis.draft is not None
    assert diagnosis.draft.fields[0].name == "dataset"
    assert diagnosis.referenced_evidence_ids == ["e1", "e2"]
