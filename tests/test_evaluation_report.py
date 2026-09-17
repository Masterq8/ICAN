import json

import pytest

from ican.evaluation.data import Case, digest
from ican.evaluation.report import summarize
from ican.evaluation.runner import validate_snapshot
from ican.retrieval.schema import SearchResponse


def fixture_run(monkeypatch, tmp_path):
    case = Case("q", "swin", "dev", "question?", "swin_v1", {})
    gold = {case.key: {"required_evidence": ["R1"]}}
    monkeypatch.setattr(
        "ican.evaluation.report.load_inputs", lambda _: ([case], gold, {})
    )
    monkeypatch.setattr("ican.evaluation.report.load_chunk_registry", lambda _: {})
    monkeypatch.setattr("ican.evaluation.runner.load_chunk_registry", lambda _: {})
    corpus_dir = tmp_path / "data/processed/qasper_external/v1"
    corpus_dir.mkdir(parents=True)
    for split in ["train", "validation"]:
        (corpus_dir / f"{split}_corpus.jsonl").write_text("", encoding="utf-8")
    eval_dir = tmp_path / "data/eval"
    eval_dir.mkdir(parents=True)
    (eval_dir / "swin_evidence.json").write_text(
        json.dumps(
            {
                "evidence": [
                    {"id": "R1", "type": "repository", "path": "f.py", "lines": "1-2"}
                ]
            }
        ),
        encoding="utf-8",
    )
    vendor = tmp_path / "third_party/qasper"
    vendor.mkdir(parents=True)
    (vendor / "evaluator.py").write_text("test-provenance", encoding="utf-8")
    response = SearchResponse(
        index_fingerprint="a" * 64,
        collection=case.collection,
        query=case.question,
        filters={},
        results=[],
    )
    snapshot = tmp_path / "retrieval.jsonl"
    snapshot.write_text(
        json.dumps(
            {
                "key": case.key,
                "case": case.record(),
                "response": response.model_dump(),
                "elapsed_seconds": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "input_sha256": {},
        "protocol": {"variants": ["adapter"], "k": [8]},
        "retrieval_sha256": digest(snapshot),
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return case, manifest


def test_interrupted_started_request_remains_in_failure_denominator(
    monkeypatch, tmp_path
):
    case, _ = fixture_run(monkeypatch, tmp_path)
    (tmp_path / "journal.jsonl").write_text(
        json.dumps({"event": "started", "key": case.key + "/adapter"}) + "\n",
        encoding="utf-8",
    )
    result = summarize(tmp_path, tmp_path)
    row = next(r for r in result["generation"] if r["dataset"] == "swin")
    assert (
        row["attempted_n"]
        == row["unfinished_started_n"]
        == row["failed_or_unfinished_n"]
        == 1
    )
    assert row["citation_valid_rate"] == 0
    assert row["usage_missing_n"] == 1
    assert result["incomplete"]


def test_mutated_retrieval_snapshot_is_rejected(monkeypatch, tmp_path):
    case, manifest = fixture_run(monkeypatch, tmp_path)
    with (tmp_path / "retrieval.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="snapshot changed"):
        validate_snapshot(tmp_path, tmp_path, [case], manifest)


def test_retrieval_cannot_reseal_changed_snapshot(monkeypatch, tmp_path):
    from ican.evaluation.runner import retrieve

    case, manifest = fixture_run(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ican.evaluation.runner.load_inputs", lambda _: ([case], {}, {})
    )
    monkeypatch.setattr(
        "ican.evaluation.runner.protocol", lambda *args: manifest["protocol"]
    )
    with (tmp_path / "retrieval.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="snapshot changed"):
        retrieve(tmp_path, tmp_path, None, ["adapter"])
