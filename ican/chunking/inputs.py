"""Read exact allowlisted, hash-checked parent units; never load eval labels."""

from __future__ import annotations

import json
from pathlib import Path

from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined
from ican.ingestion.schema import ParsedUnit, SourceRecord

from .schema import DatasetConfig, ParentUnit


def read_lines(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_dataset(
    root: Path, dataset: DatasetConfig
) -> tuple[dict[str, list[ParentUnit]], dict]:
    manifest_path = confined(root, dataset.parent_manifest, "data/processed")
    if sha256(manifest_path.read_bytes()) != dataset.expected_manifest_sha256:
        raise ValueError("Parent manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_records = {}
    hashes = {}
    if dataset.kind == "parsed":
        if manifest.get("status") != "passed" or manifest.get("errors") != 0:
            raise ValueError("Parent parsing did not pass")
        if not dataset.sources:
            raise ValueError("Parsed dataset requires source records")
        source_path = confined(root, dataset.sources, "data/processed")
        expected = manifest["artifact_sha256"].get(source_path.name)
        if not expected or sha256(source_path.read_bytes()) != expected:
            raise ValueError("Source records hash mismatch")
        records = [SourceRecord.model_validate(row) for row in read_lines(source_path)]
        source_records = {row.source_id: row for row in records}
        if len(source_records) != len(records):
            raise ValueError("Duplicate source IDs")
        hashes[dataset.sources] = expected
    all_units, seen_ids = {}, set()
    for split, relative in dataset.inputs.items():
        path = confined(root, relative, "data/processed")
        if path.suffix != ".jsonl":
            raise ValueError("Only JSONL parent inputs are allowed")
        expected = manifest["artifact_sha256"].get(
            path.name if dataset.kind == "parsed" else relative
        )
        if dataset.kind == "qasper" and relative not in manifest["index_allowlist"]:
            raise ValueError("QASPER input is outside corpus allowlist")
        if not expected or sha256(path.read_bytes()) != expected:
            raise ValueError(f"Parent input hash mismatch: {relative}")
        hashes[relative] = expected
        rows = read_lines(path)
        units = []
        for row in rows:
            if {"answers", "question", "qas", "evidence", "gold_evidence"} & row.keys():
                raise ValueError("Evaluation labels cannot be loaded as corpus")
            if dataset.kind == "parsed":
                parsed = ParsedUnit.model_validate(row)
                record = source_records.get(parsed.source_id)
                if record is None or record.status not in {"parsed", "partial"}:
                    raise ValueError("Parent source missing or failed")
                if parsed.version != record.version or parsed.path != record.path:
                    raise ValueError("Parent/source identity mismatch")
                location = (
                    {"page": parsed.page}
                    if parsed.page
                    else {"line_start": parsed.line_start, "line_end": parsed.line_end}
                )
                unit = ParentUnit(
                    unit_id=parsed.unit_id,
                    source_id=parsed.source_id,
                    source_type=parsed.source_type,
                    input_path=relative,
                    path=parsed.path,
                    source_url=record.url,
                    version=parsed.version,
                    source_sha256=record.raw_sha256,
                    text=parsed.text,
                    text_sha256=parsed.text_sha256,
                    location=location,
                    structures=parsed.structures,
                    metadata=parsed.metadata,
                )
            else:
                if (
                    row["split"] != split
                    or row["dataset_revision"] != manifest["dataset_revision"]
                ):
                    raise ValueError("QASPER split/revision mismatch")
                if (
                    "page" in row["location"]
                    or not {"section_index", "caption_index"} & row["location"].keys()
                ):
                    raise ValueError(
                        "QASPER has no physical page; paragraph/caption location required"
                    )
                unit = ParentUnit(
                    unit_id=row["unit_id"],
                    source_id=f"qasper:{row['paper_id']}",
                    source_type="paper",
                    input_path=relative,
                    path=f"qasper/{row['paper_id']}",
                    source_url=row["source_url"],
                    version=row["dataset_revision"],
                    text=row["text"],
                    text_sha256=row["text_sha256"],
                    title=row["title"],
                    location={"paper_id": row["paper_id"], **row["location"]},
                    metadata={
                        "section_path": row["section"].split(" ::: "),
                        "source_corpus_sha256": expected,
                    },
                )
            if unit.text_sha256 != sha256(unit.text.encode("utf-8")):
                raise ValueError("Parent text SHA-256 mismatch")
            if unit.unit_id in seen_ids:
                raise ValueError("Duplicate parent unit IDs across inputs")
            seen_ids.add(unit.unit_id)
            units.append(unit)
        # Physical page order, not lexicographic unit ID, determines inherited
        # headings. Repository file order remains stable.
        units.sort(key=lambda u: (u.source_id, u.location.get("page", 0), u.unit_id))
        titles = {}
        if dataset.kind == "parsed":
            for u in units:
                if u.source_type == "paper" and u.location["page"] == 1:
                    heading = next(
                        (s for s in u.structures if s.kind == "section_header"), None
                    )
                    if heading:
                        titles[u.source_id] = u.text[
                            heading.char_start : heading.char_end
                        ]
            for u in units:
                u.title = titles.get(u.source_id, "")
        all_units[split] = units
    if dataset.kind == "qasper":
        paper_splits = {}
        for split, units in all_units.items():
            for unit in units:
                paper = unit.location["paper_id"]
                if paper in paper_splits and paper_splits[paper] != split:
                    raise ValueError("Cross-split paper leakage")
                paper_splits[paper] = split
    return all_units, hashes
