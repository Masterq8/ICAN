from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Case:
    id: str
    dataset: str
    split: str
    question: str
    collection: str
    filters: dict

    @property
    def key(self) -> str:
        return f"{self.dataset}/{self.split}/{self.id}"

    def request(self) -> dict:
        return {
            "query": self.question,
            "collection": self.collection,
            "limit": 8,
            "filters": self.filters,
        }

    def record(self) -> dict:
        return asdict(self)


def load_inputs(root: Path):
    swin_manifest = json.loads(
        (root / "data/eval/swin_eval_manifest.json").read_text(encoding="utf-8")
    )
    qasper_manifest = json.loads(
        (root / "data/catalog/qasper-external.json").read_text(encoding="utf-8")
    )
    fixed = {
        swin_manifest["files"][key]["path"]: swin_manifest["files"][key]["sha256"]
        for key in ["dev", "evidence", "test"]
    }
    fixed.update(qasper_manifest["artifact_sha256"])
    index_config = json.loads(
        (root / "configs/indexing/v1.json").read_text(encoding="utf-8")
    )
    for source in index_config["sources"]:
        directory = source["directory"]
        manifest_path = directory + "/chunk_manifest.json"
        if digest(root / manifest_path) != source["expected_manifest_sha256"]:
            raise ValueError("Fixed chunk manifest changed")
        fixed[manifest_path] = source["expected_manifest_sha256"]
        chunk_manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
        fixed[directory + "/chunks.jsonl"] = chunk_manifest["artifacts_sha256"][
            "chunks.jsonl"
        ]
    for path, expected in fixed.items():
        if digest(root / path) != expected:
            raise ValueError(f"Fixed evaluation input changed: {path}")
    # Frozen test is hashed above, never parsed. Only allowed dev/train/validation gold is read.
    swin = read_jsonl(root / swin_manifest["files"]["dev"]["path"])
    train = sorted(
        read_jsonl(root / "data/eval/qasper_external/v1/train_questions.jsonl"),
        key=lambda item: item["question_id"],
    )[:3]
    validation = read_jsonl(
        root / "data/eval/qasper_external/v1/validation_questions.jsonl"
    )
    cases, gold = [], {}
    for split, items in [("train", train), ("dev", swin), ("validation", validation)]:
        for item in items:
            is_swin = split == "dev"
            case = Case(
                item["id"] if is_swin else item["question_id"],
                "swin" if is_swin else "qasper",
                split,
                item["question"],
                "swin_v1" if is_swin else f"qasper_{split}_v1",
                {}
                if is_swin
                else {
                    "source_types": ["paper"],
                    "path_prefixes": [f"qasper/{item['paper_id']}"],
                },
            )
            cases.append(case)
            gold[case.key] = item
    if len(swin) != 12 or len(validation) != 32 or len(train) != 3:
        raise ValueError("Unexpected fixed evaluation counts")
    return cases, gold, fixed


def load_chunk_registry(root: Path) -> dict[str, dict]:
    paths = [
        "data/processed/swin/chunks/v1/chunks.jsonl",
        "data/processed/qasper_external/chunks/v1/chunks.jsonl",
    ]
    rows = [row for path in paths for row in read_jsonl(root / path)]
    return {row["chunk_id"]: row for row in rows}
