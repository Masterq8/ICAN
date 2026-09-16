from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pymupdf
import pytest

from ican.ingestion.parsers import (
    config_structures,
    markdown_structures,
    parse_pdf,
    parse_text_file,
    sha256,
)
from ican.ingestion.pipeline import ingest
from ican.ingestion.schema import IngestionConfig


def test_code_locations_include_decorators_and_original_crlf(tmp_path):
    raw = b"# coding: utf-8\r\n@decorate\r\nclass A:\r\n    def run(self):\r\n        return 1\r\n"
    path = tmp_path / "a.py"
    path.write_bytes(raw)
    unit, issues = parse_text_file(
        path, source_id="a", relative_path="a.py", version="fixed"
    )
    assert not issues
    assert unit.text.encode() == raw
    symbols = {s.name: s for s in unit.structures}
    assert symbols["A"].line_start == 2
    assert symbols["A.run"].line_start == 4
    assert (
        unit.text[symbols["A.run"].char_start : symbols["A.run"].char_end]
        == "    def run(self):\r\n        return 1\r\n"
    )


def test_yaml_field_evidence_and_recursive_alias():
    text = "MODEL:\n  SWIN:\n    DEPTHS: [2, 2, 6, 2]\nloop: &loop\n  ref: *loop\n"
    spans = {s.name: s for s in config_structures(text)}
    field = spans["MODEL.SWIN.DEPTHS"]
    assert field.line_start == 3
    assert "DEPTHS: [2, 2, 6, 2]" in text[field.char_start : field.char_end]
    assert len(spans) < 10


def test_invalid_structure_keeps_text_without_execution(tmp_path):
    text = "from pathlib import Path\nPath('SHOULD_NOT_EXIST').write_text('executed')\ndef broken(\n"
    path = tmp_path / "invalid.py"
    path.write_bytes(text.encode("utf-8"))
    unit, issues = parse_text_file(
        path, source_id="bad", relative_path="invalid.py", version="v"
    )
    assert unit.text == text and not unit.structures
    assert issues[0]["code"] == "structure_parse_failed"
    assert not Path("SHOULD_NOT_EXIST").exists()


def test_markdown_heading_ignores_fences():
    text = "# Main\n```python\n# hidden\n```\n## Child\nhello\n# Next\n"
    spans = markdown_structures(text)
    assert [s.name for s in spans] == ["Main", "Child", "Next"]
    assert spans[0].line_end == 6


def make_pdf(path):
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text(
            (50, 60), "Wide heading across the entire document page", fontsize=18
        )
        page.insert_text((50, 110), "LEFT ONE")
        page.insert_text((350, 110), "RIGHT ONE")
        page.insert_text((50, 140), "LEFT TWO")
        page.insert_text((350, 140), "RIGHT TWO")
        doc.new_page(width=600, height=800)  # Empty page must be reported.
        doc.save(path)


def test_pdf_column_order_page_and_position(tmp_path):
    path = tmp_path / "test.pdf"
    make_pdf(path)
    units, issues = parse_pdf(
        path, source_id="pdf", relative_path="test.pdf", version="v"
    )
    assert len(units) == 1 and units[0].page == 1
    text = units[0].text
    assert (
        text.index("LEFT ONE")
        < text.index("LEFT TWO")
        < text.index("RIGHT ONE")
        < text.index("RIGHT TWO")
    )
    assert all(s.bbox and text[s.char_start : s.char_end] for s in units[0].structures)
    assert issues[0]["page"] == 2 and issues[0]["code"] == "pdf_no_text"


def setup_repo(tmp_path):
    repo = tmp_path / "data/raw/repositories/example"
    repo.mkdir(parents=True)
    for args in (
        ["init"],
        ["config", "user.name", "Ingestion Test"],
        ["config", "user.email", "test@example.invalid"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "config.yaml").write_text("MODEL:\n  NAME: tiny\n", encoding="utf-8")
    (repo / "binary.txt").write_bytes(b"bad\x00data")
    (repo / "ignore.bin").write_bytes(b"ignore")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    version = (
        subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"])
        .decode()
        .strip()
    )
    (repo / "untracked.py").write_text("secret = 'must not index'", encoding="utf-8")
    config = IngestionConfig(
        dataset_id="test",
        output_dir="data/processed/test",
        extensions=[".yaml", ".txt", ".py"],
        sources=[
            {
                "kind": "repository",
                "path": "data/raw/repositories/example",
                "version": version,
                "url": "https://example.invalid/repo",
            }
        ],
    )
    return repo, config


def test_pipeline_isolates_file_failure_and_rebuild_is_stable(tmp_path):
    _, config = setup_repo(tmp_path)
    report = ingest(tmp_path, config)
    assert report["units"] == 1 and report["errors"] == 1
    output = tmp_path / config.output_dir
    units = [
        json.loads(x)
        for x in (output / "parsed_units.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert all("untracked.py" not in u["path"] for u in units)
    assert report["skipped"][0]["reason"] == "extension_not_allowed"
    assert ingest(tmp_path, config)["artifact_sha256"] == report["artifact_sha256"]


@pytest.mark.parametrize("changed", ["commit", "tracked_text"])
def test_pipeline_rejects_version_and_tracked_edits(tmp_path, changed):
    repo, config = setup_repo(tmp_path)
    if changed == "commit":
        config.sources[0].version = "0" * 40
    else:
        (repo / "config.yaml").write_text("MODEL: hacked", encoding="utf-8")
    report = ingest(tmp_path, config)
    assert report["units"] == 0 and report["status"] == "failed"


def test_source_and_output_cannot_escape_allowlist(tmp_path):
    _, config = setup_repo(tmp_path)
    config.sources[0].path = "data/eval/answers.jsonl"
    assert ingest(tmp_path, config)["units"] == 0
    config.output_dir = "data/eval"
    with pytest.raises(ValueError, match="data/processed"):
        ingest(tmp_path, config)


def test_pdf_hash_rejected_before_extraction(tmp_path):
    path = tmp_path / "data/raw/paper.pdf"
    path.parent.mkdir(parents=True)
    make_pdf(path)
    config = IngestionConfig(
        dataset_id="test",
        output_dir="data/processed/test",
        extensions=[],
        sources=[
            {
                "kind": "paper",
                "path": "data/raw/paper.pdf",
                "version": "v",
                "url": "https://example.invalid/paper",
                "expected_sha256": "0" * 64,
            }
        ],
    )
    report = ingest(tmp_path, config)
    assert report["units"] == 0 and report["errors"] == 1
    assert sha256(path.read_bytes()) != config.sources[0].expected_sha256


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_hidden_worktree_edits_cannot_impersonate_fixed_commit(tmp_path, flag):
    repo, config = setup_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(repo), "update-index", flag, "config.yaml"], check=True
    )
    (repo / "config.yaml").write_text("MODEL: UNCOMMITTED_SECRET", encoding="utf-8")
    report = ingest(tmp_path, config)
    assert report["units"] == 0 and report["status"] == "failed"


def test_read_failure_does_not_discard_other_repository_files(tmp_path, monkeypatch):
    _, config = setup_repo(tmp_path)
    original = Path.read_bytes

    def read(path):
        if path.name == "binary.txt":
            raise PermissionError("fixture read failure")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    report = ingest(tmp_path, config)
    assert report["units"] == 1 and report["errors"] == 1


def test_oversized_files_are_not_read(tmp_path, monkeypatch):
    _, config = setup_repo(tmp_path)
    config.max_file_bytes = 10
    original = Path.read_bytes

    def read(path):
        assert path.name != "config.yaml", "Oversized source should not be read"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    report = ingest(tmp_path, config)
    assert any(s["reason"] == "size_limit" for s in report["skipped"])
