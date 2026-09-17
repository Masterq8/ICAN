from __future__ import annotations

import json
from contextlib import closing

import numpy as np
import pytest
from qdrant_client import QdrantClient

from ican.chunking.pipeline import build_all
from ican.chunking.schema import ChunkConfig, DatasetConfig
from ican.indexing import inputs as index_inputs
from ican.indexing.inputs import load_chunks, point_id
from ican.indexing.model import DenseEncoder, check_model_files, checked_vectors
from ican.indexing.pipeline import build_index, index_directory, index_identity
from ican.indexing.schema import IndexConfig
from ican.indexing.verification import verify_artifacts
from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import write_json, write_jsonl
from ican.ingestion.schema import ParsedUnit, SourceRecord


def config():
    return IndexConfig.model_validate(
        {
            "model": {
                "repository": "BAAI/bge-m3",
                "revision": "a" * 40,
                "local_path": "data/cache/model",
                "ledger_path": "data/catalog/model.json",
                "files": {"config.json": {"size": 1, "sha256": sha256(b"x")}},
                "device": "cpu",
                "precision": "float32",
            },
            "chunk_config": "configs/chunking/v1.json",
            "storage_root": "data/indexes/test",
            "sources": [
                {
                    "dataset_id": "d",
                    "directory": "data/processed/chunks",
                    "expected_manifest_sha256": "b" * 64,
                    "collections": {
                        "default": "swin_v1",
                        "train": "qasper_train_v1",
                        "validation": "qasper_validation_v1",
                    },
                }
            ],
        }
    )


def rows():
    result = []
    for collection, split in [
        ("swin_v1", "default"),
        ("qasper_train_v1", "train"),
        ("qasper_validation_v1", "validation"),
    ]:
        for index in range(2):
            text = f"{collection} original evidence {index}"
            identifier = f"chunk:{split}:{index}"
            result.append(
                {
                    "id": point_id(collection, identifier),
                    "collection": collection,
                    "chunk": {
                        "chunk_id": identifier,
                        "embedding_text": text,
                        "review_required": bool(index),
                        "location": {"page": index + 1},
                        "split": split,
                    },
                    "embedding_input_sha256": sha256(text.encode()),
                }
            )
    return sorted(result, key=lambda r: (r["collection"], r["chunk"]["chunk_id"]))


class FakeEncoder:
    def __init__(self):
        self.descriptor = {"purpose": "unit test only"}

    def lengths(self, texts):
        return [len(t.split()) + 2 for t in texts]

    def encode(self, texts):
        vectors = np.zeros((len(texts), 1024), dtype=np.float32)
        for index, text in enumerate(texts):
            vectors[index, int(sha256(text.encode())[:8], 16) % 1024] = 1
        return vectors


def build(root, *, cfg=None, encoder=None):
    return build_index(
        root,
        cfg or config(),
        rows=rows(),
        snapshots={"input": "fixed"},
        ledger_sha256="c" * 64,
        encoder=encoder or FakeEncoder(),
    )


def test_persistent_collections_payloads_and_reuse_without_reencoding(tmp_path):
    cfg = config()
    result = build(tmp_path)
    directory = tmp_path / result["directory"]
    identity = index_identity(cfg, {"input": "fixed"}, "c" * 64)
    report = verify_artifacts(directory, rows(), cfg, identity)
    assert report["collections"] == {
        "swin_v1": 2,
        "qasper_train_v1": 2,
        "qasper_validation_v1": 2,
    }
    assert report["all_payloads_and_vectors_checked"]
    assert build(tmp_path, encoder=object())["status"] == "reused"


def test_changed_input_identity_creates_a_different_version(tmp_path):
    cfg = config()
    a = index_identity(cfg, {"chunks": "old"}, "c" * 64)
    b = index_identity(cfg, {"chunks": "new"}, "c" * 64)
    assert index_directory(tmp_path, cfg, a) != index_directory(tmp_path, cfg, b)


@pytest.mark.parametrize("kind", ["nan", "zero", "wrong_shape"])
def test_invalid_vectors_are_rejected(kind):
    values = np.ones((2, 1024), dtype=np.float32)
    if kind == "nan":
        values[0, 0] = np.nan
    elif kind == "zero":
        values[0] = 0
    else:
        values = values[:, :-1]
    with pytest.raises(ValueError):
        checked_vectors(values, 2, 1024)


def test_long_input_fails_before_encoding_and_never_publishes(tmp_path):
    class Oversize(FakeEncoder):
        def lengths(self, texts):
            return [8193] * len(texts)

        def encode(self, texts):
            pytest.fail("Must check length before encoding")

    with pytest.raises(ValueError, match="tokenizer lengths"):
        build(tmp_path, encoder=Oversize())
    manifests = list((tmp_path / config().storage_root).rglob("index_manifest.json"))
    assert not manifests
    failed = list((tmp_path / config().storage_root).rglob("build_report.json"))
    assert len(failed) == 1 and json.loads(failed[0].read_text())["status"] == "failed"


def test_dense_encoder_token_count_keeps_special_tokens_and_rejects_truncation():
    encoder = DenseEncoder.__new__(DenseEncoder)
    encoder.config = config().model
    calls = []

    def tokenizer(texts, **kwargs):
        calls.append(kwargs)
        return {"input_ids": [list(range(8193)) for _ in texts]}

    encoder.tokenizer = tokenizer
    with pytest.raises(ValueError, match="actual model tokenizer limit"):
        encoder.lengths(["original source"])
    assert calls[0] == {
        "add_special_tokens": True,
        "truncation": False,
        "padding": False,
    }


def test_model_content_tampering_is_rejected(tmp_path):
    cfg = config().model
    directory = tmp_path / cfg.local_path
    directory.mkdir(parents=True)
    (directory / "config.json").write_bytes(b"x")
    check_model_files(tmp_path, cfg)
    (directory / "config.json").write_bytes(b"y")
    with pytest.raises(ValueError, match="SHA-256"):
        check_model_files(tmp_path, cfg)


def test_unlisted_model_weights_cannot_override_verified_weights(tmp_path):
    cfg = config().model
    directory = tmp_path / cfg.local_path
    directory.mkdir(parents=True)
    (directory / "config.json").write_bytes(b"x")
    (directory / "model.safetensors").write_bytes(b"unverified override")
    with pytest.raises(ValueError, match="Unverified model file"):
        check_model_files(tmp_path, cfg)


def test_persisted_payload_tampering_is_rejected(tmp_path):
    cfg = config()
    result = build(tmp_path)
    directory = tmp_path / result["directory"]
    target = rows()[0]
    with closing(QdrantClient(path=str(directory / "qdrant"))) as client:
        client.set_payload(
            target["collection"], payload={"collection": "wrong"}, points=[target["id"]]
        )
    with pytest.raises(ValueError, match="payload/collection"):
        verify_artifacts(
            directory, rows(), cfg, index_identity(cfg, {"input": "fixed"}, "c" * 64)
        )


def test_vector_artifact_tampering_is_rejected(tmp_path):
    cfg = config()
    result = build(tmp_path)
    directory = tmp_path / result["directory"]
    with (directory / "vectors.npy").open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="artifact hash"):
        verify_artifacts(
            directory, rows(), cfg, index_identity(cfg, {"input": "fixed"}, "c" * 64)
        )


def test_storage_confinement(tmp_path):
    with pytest.raises(ValueError, match="data/indexes"):
        build(
            tmp_path, cfg=config().model_copy(update={"storage_root": "data/raw/wrong"})
        )


def test_collection_names_must_be_disjoint():
    raw = config().model_dump()
    raw["sources"][0]["collections"] = {"train": "same", "validation": "same"}
    with pytest.raises(ValueError, match="disjoint"):
        IndexConfig.model_validate(raw)


def corpus_fixture(root, monkeypatch):
    directory = root / "data/processed/parents"
    directory.mkdir(parents=True)
    text = "WINDOW_SIZE = 7\n"
    unit = ParsedUnit(
        unit_id="u",
        source_id="s",
        source_type="code",
        path="official/model.py",
        version="fixed",
        text=text,
        text_sha256=sha256(text.encode()),
        line_start=1,
        line_end=1,
    )
    source = SourceRecord(
        source_id="s",
        kind="repository",
        path=unit.path,
        version=unit.version,
        url="https://example.org/official",
        raw_sha256=sha256(text.encode()),
        status="parsed",
        unit_count=1,
    )
    write_jsonl(directory / "units.jsonl", [unit])
    write_jsonl(directory / "sources.jsonl", [source])
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
        dataset_id="d",
        kind="parsed",
        parent_manifest="data/processed/parents/report.json",
        expected_manifest_sha256=sha256((directory / "report.json").read_bytes()),
        inputs={"default": "data/processed/parents/units.jsonl"},
        sources="data/processed/parents/sources.jsonl",
        output_dir="data/processed/chunks",
    )
    chunk_config = ChunkConfig(datasets=[dataset])
    build_all(root, chunk_config)
    path = root / "configs/chunking/v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(chunk_config.model_dump_json(), encoding="utf-8")
    frozen = root / "data/eval/swin_test.jsonl"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(b"frozen fixture")
    digest = sha256(b"frozen fixture")
    monkeypatch.setattr(index_inputs, "FROZEN_SHA256", digest)
    output = root / dataset.output_dir
    manifest_hash = sha256((output / "chunk_manifest.json").read_bytes())
    validation = json.loads((output / "chunk_report.json").read_text(encoding="utf-8"))[
        "validation"
    ]
    write_json(
        output / "verification_report.json",
        {
            **validation,
            "chunk_manifest_sha256": manifest_hash,
            "frozen_test_sha256": digest,
        },
    )
    cfg = config().model_dump()
    cfg["sources"][0].update(
        expected_manifest_sha256=manifest_hash, collections={"default": "swin_v1"}
    )
    return IndexConfig.model_validate(cfg)


def test_allowlisted_input_loader_preserves_source_and_excludes_labels(
    tmp_path, monkeypatch
):
    cfg = corpus_fixture(tmp_path, monkeypatch)
    points, snapshots = load_chunks(tmp_path, cfg)
    assert len(points) == 1 and snapshots["d"]["parent_input_sha256"]
    assert points[0]["chunk"]["source_version"] == "fixed"
    assert points[0]["chunk"]["location"] == {"line_start": 1, "line_end": 1}
    assert "answers" not in points[0]["chunk"]


@pytest.mark.parametrize(
    "target,message",
    [
        ("chunks.jsonl", "artifact hash"),
        ("chunk_manifest.json", "manifest hash"),
        ("verification_report.json", "verification report"),
    ],
)
def test_input_loader_rejects_changed_snapshot_or_validation(
    tmp_path, monkeypatch, target, message
):
    cfg = corpus_fixture(tmp_path, monkeypatch)
    (tmp_path / cfg.sources[0].directory / target).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_chunks(tmp_path, cfg)


def test_input_loader_refuses_split_collection_mismatch(tmp_path, monkeypatch):
    cfg = corpus_fixture(tmp_path, monkeypatch)
    raw = cfg.model_dump()
    raw["sources"][0]["collections"] = {"validation": "qasper_validation_v1"}
    with pytest.raises(ValueError, match="exact corpus splits"):
        load_chunks(tmp_path, IndexConfig.model_validate(raw))


def test_eval_integrity_is_checked_without_loading_answers(tmp_path, monkeypatch):
    cfg = corpus_fixture(tmp_path, monkeypatch)
    path = tmp_path / "data/eval/external.jsonl"
    path.write_bytes(b"not loaded as corpus")
    cfg = cfg.model_copy(
        update={
            "evaluation_sha256": {"data/eval/external.jsonl": sha256(path.read_bytes())}
        }
    )
    assert len(load_chunks(tmp_path, cfg)[0]) == 1
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Evaluation snapshot"):
        load_chunks(tmp_path, cfg)
