"""Auditable helpers for the P4.6 research-card quality acceptance run."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

FIELD_NAMES = {
    "task",
    "model",
    "dataset",
    "input_setting",
    "training",
    "metric",
    "result",
    "limitation",
    "code_availability",
}


def evidence_identity(evidence):
    """Return source identity and a text digest without copying source text."""

    return {
        "chunk_id": evidence.chunk_id,
        "source_id": evidence.source.source_id,
        "source_path": evidence.source.source_path,
        "source_version": evidence.source.source_version,
        "location": evidence.source.location,
        "text_sha256": hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(),
    }


def _collect(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key == "source_id"
                and isinstance(item, str)
                and item.startswith("qasper:")
            ):
                found.add(item)
            _collect(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect(item, found)


def collect_prior_source_ids(roots: list[Path]) -> set[str]:
    """Collect QASPER source IDs from completed/started run artifacts."""

    found: set[str] = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                values = (
                    [json.loads("\n".join(lines))]
                    if path.suffix == ".json"
                    else [json.loads(line) for line in lines if line.strip()]
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            for value in values:
                _collect(value, found)
    return found


def _rate(numerator: int, denominator: int):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def score_quality_review(cases: dict, review: dict, *, total_cases: int):
    """Calculate quality metrics while keeping failed submissions out of field scores."""

    if set(cases) != set(review.get("cases", {})):
        raise ValueError("Manual review must cover every frozen case")
    successes = sum(bool(case.get("tool_success")) for case in cases.values())
    support_yes = support_total = 0
    type_yes = type_total = 0
    missing_yes = missing_total = 0
    present_yes = present_total = 0
    confusions = Counter()

    for key, case in cases.items():
        if not case.get("tool_success"):
            continue
        item = review["cases"][key]
        submitted = list(case.get("submitted_fields", []))
        reviewed = [field["name"] for field in item.get("fields", [])]
        if len(reviewed) != len(set(reviewed)) or set(reviewed) != set(submitted):
            raise ValueError(f"{key}: reviewed fields must equal submitted fields")
        expected = set(item.get("expected_present_fields", []))
        if not expected <= FIELD_NAMES:
            raise ValueError(f"{key}: unknown expected field")
        submitted_set = set(submitted)
        omitted_present = set(item.get("omitted_present_fields", []))
        if omitted_present != expected - submitted_set:
            raise ValueError(f"{key}: omitted present fields do not match gold")

        for field in item["fields"]:
            support_total += 1
            type_total += 1
            support_yes += bool(field["evidence_supported"])
            type_yes += bool(field["type_correct"])
            if not field["type_correct"]:
                confusions[f"{field['name']}->{field['correct_type']}"] += 1

        gold_absent = FIELD_NAMES - expected
        missing_total += len(gold_absent)
        missing_yes += len(gold_absent - submitted_set)
        present_total += len(expected)
        present_yes += len(expected & submitted_set)

    return {
        "tool_submission_success": _rate(successes, total_cases),
        "evidence_support_rate": _rate(support_yes, support_total),
        "field_classification_accuracy": _rate(type_yes, type_total),
        "missing_field_identification_rate": _rate(missing_yes, missing_total),
        "present_field_recall": _rate(present_yes, present_total),
        "confusions": dict(sorted(confusions.items())),
        "field_metrics_successful_cases_only": True,
    }
