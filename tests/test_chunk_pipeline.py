from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ican.chunking.artifacts import artifact_path
from ican.chunking.inputs import load_dataset
from ican.chunking.pipeline import build_all, build_dataset
from ican.chunking.schema import ChunkConfig, DatasetConfig
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import write_json, write_jsonl
from ican.ingestion.schema import ParsedUnit, SourceRecord
from scripts.check_chunk_rebuild import check


def fixture_dataset(root, *, label=False, bad_text=False):
    directory = root / "data/processed/parents/v1"
    directory.mkdir(parents=True)
    text = "MODEL:\n  WINDOW_SIZE: 7\n"
    unit = ParsedUnit(
        unit_id="u",
        source_id="s",
        source_type="config",
        path="raw/model.yaml",
        version="commit",
        text=text,
        text_sha256=sha256(b"wrong") if bad_text else sha256(text.encode()),
        line_start=1,
        line_end=2,
    ).model_dump()
    if label:
        unit["answers"] = ["gold"]
    record = SourceRecord(
        source_id="s",
        kind="repository",
        path="raw/model.yaml",
        version="commit",
        url="https://example.org/repo",
        raw_sha256=sha256(text.encode()),
        status="parsed",
        unit_count=1,
    )
    write_jsonl(directory / "units.jsonl", [unit])
    write_jsonl(directory / "sources.jsonl", [record])
    write_json(
        directory / "report.json",
        {
            "status": "passed",
            "errors": 0,
            "artifact_sha256": {
                n: sha256((directory / n).read_bytes())
                for n in ["units.jsonl", "sources.jsonl"]
            },
        },
    )
    dataset = DatasetConfig(
        dataset_id="test",
        kind="parsed",
        parent_manifest="data/processed/parents/v1/report.json",
        expected_manifest_sha256=sha256((directory / "report.json").read_bytes()),
        inputs={"default": "data/processed/parents/v1/units.jsonl"},
        sources="data/processed/parents/v1/sources.jsonl",
        output_dir="data/processed/chunks/v1",
    )
    return ChunkConfig(datasets=[dataset]), dataset


def test_rebuild_is_identical_and_parents_not_changed(tmp_path):
    config, d = fixture_dataset(tmp_path)
    build_all(tmp_path, config)
    output = tmp_path / d.output_dir
    names = [
        "chunks.jsonl",
        "chunk_manifest.json",
        "chunk_report.json",
        "review_samples.md",
    ]
    before = {n: (output / n).read_bytes() for n in names}
    build_all(tmp_path, config)
    assert before == {n: (output / n).read_bytes() for n in names}
    load_dataset(tmp_path, d)


def test_changed_input_invalidates_old_passed_manifest(tmp_path):
    config, d = fixture_dataset(tmp_path)
    build_all(tmp_path, config)
    (tmp_path / d.inputs["default"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="input hash mismatch"):
        build_all(tmp_path, config)
    assert not (tmp_path / d.output_dir / "chunk_manifest.json").exists()
    assert (
        json.loads((tmp_path / d.output_dir / "chunk_report.json").read_text())[
            "status"
        ]
        == "failed"
    )


@pytest.mark.parametrize(
    "kwargs, message", [({"label": True}, "labels"), ({"bad_text": True}, "text SHA")]
)
def test_rejects_gold_labels_and_incorrect_parent_text_hash(tmp_path, kwargs, message):
    config, _ = fixture_dataset(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=message):
        build_all(tmp_path, config)


def test_rejects_changed_manifest(tmp_path):
    config, d = fixture_dataset(tmp_path)
    (tmp_path / d.parent_manifest).write_bytes(b"{}")
    with pytest.raises(ValueError, match="manifest hash"):
        build_all(tmp_path, config)


def test_output_directory_failure_never_publishes_success(tmp_path):
    config, d = fixture_dataset(tmp_path)
    out = tmp_path / d.output_dir
    out.mkdir(parents=True)
    (out / "review_samples.md").mkdir()
    with pytest.raises(OSError):
        build_all(tmp_path, config)
    assert not (out / "chunk_manifest.json").exists()


@pytest.mark.parametrize(
    "path", ["data/processed/parents/v1", "../escape", "data/eval/new"]
)
def test_directory_confinement(tmp_path, path):
    config, d = fixture_dataset(tmp_path)
    altered = d.model_copy(update={"output_dir": path})
    with pytest.raises(ValueError):
        build_dataset(tmp_path, config, altered)


def test_outputs_cannot_collide_across_datasets(tmp_path):
    config, d = fixture_dataset(tmp_path)
    other = d.model_copy(
        update={"dataset_id": "other", "output_dir": d.output_dir + "/nested"}
    )
    with pytest.raises(ValueError, match="disjoint"):
        build_all(tmp_path, config.model_copy(update={"datasets": [d, other]}))


def test_artifact_symlink_cannot_overwrite_parent(tmp_path):
    config, d = fixture_dataset(tmp_path)
    out = tmp_path / d.output_dir
    out.mkdir(parents=True)
    target = tmp_path / d.inputs["default"]
    before = target.read_bytes()
    try:
        (out / "chunks.jsonl").symlink_to(target)
    except OSError as error:
        pytest.skip(f"OS does not allow test symlinks: {error}")
    with pytest.raises(ValueError, match="Artifact"):
        build_all(tmp_path, config)
    assert target.read_bytes() == before
    assert not (out / "chunk_manifest.json").exists()


def test_symlink_preflight_without_os_privilege(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda p: p.name == "chunks.jsonl" or original(p)
    )
    with pytest.raises(ValueError, match="Artifact"):
        artifact_path(tmp_path, "chunks.jsonl")


def test_artifact_hardlink_cannot_overwrite_parent(tmp_path):
    config, d = fixture_dataset(tmp_path)
    out = tmp_path / d.output_dir
    out.mkdir(parents=True)
    target = tmp_path / d.inputs["default"]
    before = target.read_bytes()
    os.link(target, out / "chunks.jsonl")
    with pytest.raises(ValueError, match="hard link"):
        build_all(tmp_path, config)
    assert target.read_bytes() == before
    assert not (out / "chunk_manifest.json").exists()


def qasper_fixture(root, *, shared_paper=False, fake_page=False, label=False):
    directory = root / "data/processed/external/v1"
    directory.mkdir(parents=True)
    inputs = {}
    for split in ["train", "validation"]:
        row = {
            "unit_id": f"{split}:u",
            "paper_id": "shared" if shared_paper else split,
            "split": split,
            "title": "Paper",
            "section": "Methods ::: Architecture",
            "location": {"section_index": 1, "paragraph_index": 2},
            "text": "Original paragraph",
            "text_sha256": sha256(b"Original paragraph"),
            "source_url": "https://example.org/paper",
            "dataset_revision": "fixed",
        }
        if fake_page:
            row["location"]["page"] = 1
        if label:
            row["gold_evidence"] = ["gold"]
        relative = f"data/processed/external/v1/{split}.jsonl"
        write_jsonl(root / relative, [row])
        inputs[split] = relative
    manifest = {
        "dataset_revision": "fixed",
        "index_allowlist": list(inputs.values()),
        "artifact_sha256": {
            p: sha256((root / p).read_bytes()) for p in inputs.values()
        },
    }
    write_json(directory / "manifest.json", manifest)
    d = DatasetConfig(
        dataset_id="qasper",
        kind="qasper",
        parent_manifest="data/processed/external/v1/manifest.json",
        expected_manifest_sha256=sha256((directory / "manifest.json").read_bytes()),
        inputs=inputs,
        output_dir="data/processed/external_chunks/v1",
    )
    return ChunkConfig(datasets=[d]), d


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"shared_paper": True}, "leakage"),
        ({"fake_page": True}, "physical page"),
        ({"label": True}, "labels"),
    ],
)
def test_qasper_input_guards(tmp_path, kwargs, message):
    config, _ = qasper_fixture(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=message):
        build_all(tmp_path, config)


def test_qasper_pipeline_keeps_splits_and_paragraph_locations(tmp_path):
    config, d = qasper_fixture(tmp_path)
    report = build_all(tmp_path, config)[0]
    assert report["by_split"] == {"train": 1, "validation": 1}
    chunks = [
        json.loads(line)
        for line in (tmp_path / d.output_dir / "chunks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert all(
        "page" not in c["location"] and c["source_sha256"] is None for c in chunks
    )


def test_missing_rebuild_baseline_invalidates_previous_marker(tmp_path):
    config, d = fixture_dataset(tmp_path)
    build_all(tmp_path, config)
    marker = tmp_path / d.output_dir / "rebuild_verification.json"
    marker.write_text('{"status":"passed"}', encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        check(tmp_path, config)
    assert not marker.exists()
