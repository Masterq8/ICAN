"""Verify persisted provenance against input files, not just parser internals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.ingestion.parsers import line_offsets, sha256
from ican.ingestion.pipeline import write_json
from ican.ingestion.schema import ParsedUnit, SourceRecord

FROZEN_SHA = "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"


def verify():
    output = ROOT / "data/processed/swin/v1"
    units = [
        ParsedUnit.model_validate_json(line)
        for line in (output / "parsed_units.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    sources = {
        r.source_id: r
        for r in [
            SourceRecord.model_validate_json(line)
            for line in (output / "sources.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
    }
    checks, spans = [], 0
    for unit in units:
        assert unit.source_id in sources
        assert unit.version == sources[unit.source_id].version
        assert sha256(unit.text.encode("utf-8")) == unit.text_sha256
        assert unit.path.startswith("data/raw/") and "data/eval" not in unit.path
        if unit.source_type != "paper":
            raw = (ROOT / unit.path).read_bytes()
            assert sha256(raw) == sources[unit.source_id].raw_sha256
            assert raw.decode(unit.metadata["encoding"]) == unit.text
        for span in unit.structures:
            offsets = line_offsets(unit.text)
            assert span.char_start == offsets[span.line_start - 1]
            assert span.char_end <= offsets[span.line_end]
            assert unit.text[span.char_start : span.char_end].strip()
            if span.bbox:
                left, top, right, bottom = span.bbox
                assert 0 <= left < right <= unit.metadata["page_width"] + 1
                assert 0 <= top < bottom <= unit.metadata["page_height"] + 1
            spans += 1
    checks.append(
        "source registration, input/text hashes, version, line/character positions and PDF bounding boxes"
    )
    assert sorted(u.page for u in units if u.source_type == "paper") == list(
        range(1, 15)
    )
    checks.append("14 physical PDF pages present")
    assert sha256((ROOT / "data/eval/swin_test.jsonl").read_bytes()) == FROZEN_SHA
    checks.append("Swin frozen test SHA-256 unchanged")
    catalog = json.loads(
        (ROOT / "data/catalog/qasper-external.json").read_text(encoding="utf-8")
    )
    assert not set(catalog["selected_papers"]["train"]) & set(
        catalog["selected_papers"]["validation"]
    )
    for relative, expected in catalog["artifact_sha256"].items():
        assert sha256((ROOT / relative).read_bytes()) == expected
    external_ids = {}
    for relative in catalog["index_allowlist"]:
        for line in (ROOT / relative).read_text(encoding="utf-8").splitlines():
            unit = json.loads(line)
            assert not {"answers", "question", "qas", "evidence"} & unit.keys()
            assert unit["unit_id"] not in external_ids
            external_ids[unit["unit_id"]] = unit
    for relative in catalog["evaluation_only"]:
        for line in (ROOT / relative).read_text(encoding="utf-8").splitlines():
            question = json.loads(line)
            for answer in question["answers"]:
                for unit_id in answer["evidence_unit_ids"]:
                    assert external_ids[unit_id]["paper_id"] == question["paper_id"]
                    assert external_ids[unit_id]["split"] == question["split"]
    checks.append(
        "QASPER artifacts, cross-split isolation, gold-label separation and evidence registration"
    )
    report = {
        "status": "passed",
        "swin_units": len(units),
        "swin_spans": spans,
        "qasper_units": len(external_ids),
        "checks": checks,
    }
    write_json(output / "verification_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verify()
