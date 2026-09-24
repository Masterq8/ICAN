from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from scripts.validate_vision_mamba_dev import validate

ROOT = Path(__file__).resolve().parents[1]


def evidence_data() -> dict:
    return json.loads(
        (ROOT / "data/eval/vision_mamba_evidence.json").read_text(encoding="utf-8")
    )


def questions_data() -> list[dict]:
    path = ROOT / "data/eval/vision_mamba_dev.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_current_vision_mamba_dataset_is_source_bound() -> None:
    assert validate(ROOT) == []


def test_wrong_pdf_page_and_code_range_are_rejected() -> None:
    data = copy.deepcopy(evidence_data())
    next(item for item in data["evidence"] if item["id"] == "VP01")["page"] = 7
    next(item for item in data["evidence"] if item["id"] == "VR01")["lines"] = [
        9000,
        9001,
    ]
    errors = validate(ROOT, evidence_data=data)
    assert any("VP01" in error and "page" in error for error in errors)
    assert any("VR01" in error and "lines" in error for error in errors)


def test_mutated_map_pin_is_rejected() -> None:
    data = copy.deepcopy(evidence_data())
    data["pdf_sha256"] = "0" * 64
    data["repo_commit"] = "0" * 40
    errors = validate(ROOT, evidence_data=data)
    assert any("PDF SHA-256" in error for error in errors)
    assert any("repository HEAD" in error for error in errors)


def test_cross_variant_source_and_missing_question_evidence_are_rejected() -> None:
    data = copy.deepcopy(evidence_data())
    next(item for item in data["evidence"] if item["id"] == "VR01")["source_path"] = (
        "data/raw/repositories/Vim/seg/backbone/vim.py"
    )
    questions = copy.deepcopy(questions_data())
    questions[0]["gold_claims"][0]["evidence_ids"] = ["VR99"]
    errors = validate(ROOT, evidence_data=data, questions=questions)
    assert any("VR01" in error and "source_path" in error for error in errors)
    assert any("VR99" in error for error in errors)


def test_duplicate_question_and_leakage_group_are_rejected() -> None:
    questions = copy.deepcopy(questions_data())
    questions[1]["id"] = questions[0]["id"]
    questions[1]["leakage_group"] = questions[0]["leakage_group"]
    errors = validate(ROOT, questions=questions)
    assert any("duplicate question id" in error for error in errors)
    assert any("duplicate leakage_group" in error for error in errors)


def test_comparison_card_uses_known_evidence_and_current_index_blocks() -> None:
    card = (ROOT / "docs/vision-mamba-swin-comparison.md").read_text(encoding="utf-8")
    vim_ids = {item["id"] for item in evidence_data()["evidence"]}
    swin_ids = {
        item["id"]
        for item in json.loads(
            (ROOT / "data/eval/swin_evidence.json").read_text(encoding="utf-8")
        )["evidence"]
    }
    assert set(re.findall(r"\bV[PR]\d{2}\b", card)) <= vim_ids
    assert set(re.findall(r"\b[PR]\d{2}\b", card)) <= swin_ids
    for prefix, corpus in (("Vim", "vision_mamba"), ("Swin", "swin")):
        chunks = {
            json.loads(line)["chunk_id"]
            for line in (ROOT / f"data/processed/{corpus}/chunks/v2/chunks.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        }
        rows = [line for line in card.splitlines() if line.startswith(f"| {prefix} `")]
        assert rows
        for row in rows:
            assert set(re.findall(r"chunk:[0-9a-f]{64}", row)) <= chunks
