"""Prepare, run once, seal, and score the P4.6 v2 quality gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.research_card import collect_prior_source_ids
from ican.api.app import load_config as load_index_config
from ican.agent.journal import PaidJournal
from ican.evaluation.data import digest
from ican.research.auto_schema import AutoCardRequest
from ican.research.auto_service import ResearchAutoService
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.hybrid import HybridEvidenceSearchService

DEFAULT_CONFIG = ROOT / "configs/evaluation/p46-quality-v2.json"
EXPECTED_THRESHOLDS = {
    "tool_submission_success": 0.875,
    "evidence_support_rate": 0.90,
    "field_classification_accuracy": 0.85,
    "missing_field_identification_rate": 0.85,
}
RUN_DIR = ROOT / "data/processed/evaluation/p46-quality-v2"
RUNTIME_DIR = RUN_DIR / "runtime"
FROZEN_CASES = RUNTIME_DIR / "frozen-cases.json"
CORPUS_PATH = ROOT / "data/processed/qasper_external/v1/train_corpus.jsonl"


def normalize_source_id(value: str) -> str:
    value = str(value).strip()
    return value if value.startswith("qasper:") else f"qasper:{value}"


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value, *, exclusive: bool = False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def assert_clean_source_tree():
    output = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    )
    runtime_prefix = RUNTIME_DIR.relative_to(ROOT).as_posix() + "/"
    dirty = []
    for line in output.splitlines():
        path = line[3:].strip().replace("\\", "/")
        if not path.startswith(runtime_prefix):
            dirty.append(path)
    if dirty:
        raise ValueError(f"Source tree must be clean before prepare: {dirty[:8]}")


def source_hashes(config_path: Path) -> dict[str, str]:
    paths = [
        config_path,
        ROOT / "configs/agent/v2.json",
        ROOT / "configs/chunking/v1.json",
        ROOT / "configs/indexing/v1.json",
        ROOT / "ican/research/auto_schema.py",
        ROOT / "ican/research/auto_service.py",
        ROOT / "ican/research/field_rules.py",
        ROOT / "ican/research/submission.py",
        ROOT / "ican/evaluation/research_card.py",
        ROOT / "ican/evaluation/research_audit.py",
        ROOT / "scripts/evaluate_research_cards_v2.py",
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def services(config: dict, *, paid: bool = False) -> ResearchAutoService:
    index_config = load_index_config(ROOT)
    evidence = HybridEvidenceSearchService(ROOT, index_config)
    research = ResearchService(
        ROOT,
        index_config,
        evidence,
        store=ResearchStore(RUNTIME_DIR / "records"),
    )
    kwargs = {"trace_directory": RUNTIME_DIR / "traces"}
    if paid:
        kwargs["journal"] = PaidJournal(
            RUNTIME_DIR / "call-journal.jsonl", config["max_paid_calls"]
        )
    auto = ResearchAutoService(ROOT, index_config, evidence, research, **kwargs)
    auto.config.answer_model = config["model"]
    return auto


def validate_contract(config: dict, *, prior_source_ids: set[str]) -> dict:
    value = copy.deepcopy(config)
    cases = value.get("cases", [])
    if len(cases) != 8:
        raise ValueError("P4.6 v2 requires exactly eight cases")
    for case in cases:
        case["source_id"] = normalize_source_id(case.get("source_id", ""))
    ids = [case["source_id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("P4.6 v2 cases must use distinct source IDs")
    if value.get("split") != "train":
        raise ValueError("P4.6 v2 split must be train")
    if value.get("model") != "deepseek-v4-pro":
        raise ValueError("P4.6 v2 model must be deepseek-v4-pro")
    if value.get("max_paid_calls") != 8:
        raise ValueError("P4.6 v2 paid call cap must be eight")
    if value.get("retry_limit") != 0:
        raise ValueError("P4.6 v2 retry limit must be zero")
    if value.get("thresholds") != EXPECTED_THRESHOLDS:
        raise ValueError("P4.6 v2 quality thresholds differ from the frozen contract")
    prior = {normalize_source_id(item) for item in prior_source_ids}
    overlap = sorted(set(ids) & prior)
    if overlap:
        raise ValueError(f"Quality cases were used by prior runs: {overlap}")
    return value


def load_contract(path: Path = DEFAULT_CONFIG) -> dict:
    prior = collect_prior_source_ids(
        [
            ROOT / "data/processed/evaluation",
            ROOT / "data/processed/research",
        ]
    )
    return validate_contract(read_json(path), prior_source_ids=prior)


def prepare(config_path: Path = DEFAULT_CONFIG):
    assert_clean_source_tree()
    config_path = config_path.resolve()
    config = load_contract(config_path)
    if FROZEN_CASES.exists():
        raise ValueError("P4.6 v2 frozen cases already exist")
    auto = services(config)
    cases = []
    fingerprints = set()
    for configured in config["cases"]:
        request = AutoCardRequest(
            query=configured["query"],
            collection=config["collection"],
            source_id=configured["source_id"],
        )
        candidate, fingerprint = auto._paper_evidence(request)
        if candidate.title != configured["title"]:
            raise ValueError(f"{configured['key']}: title differs from the corpus")
        if len(candidate.evidence) != 6:
            raise ValueError(f"{configured['key']}: expected six evidence items")
        ids = [item.chunk_id for item in candidate.evidence]
        if len(set(ids)) != 6 or any(not item.text.strip() for item in candidate.evidence):
            raise ValueError(f"{configured['key']}: invalid frozen evidence")
        fingerprints.add(fingerprint)
        cases.append(
            {
                "key": configured["key"],
                "request": request.model_dump(mode="json"),
                "title": candidate.title,
                "source_path": candidate.source_path,
                "source_version": candidate.source_version,
                "index_fingerprint": fingerprint,
                "evidence": [item.model_dump(mode="json") for item in candidate.evidence],
                "evidence_sha256": {
                    item.chunk_id: text_digest(item.text) for item in candidate.evidence
                },
            }
        )
    if len(fingerprints) != 1:
        raise ValueError("Frozen papers resolved against different indexes")
    payload = {
        "version": config["version"],
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit(),
        "model": config["model"],
        "max_paid_calls": config["max_paid_calls"],
        "retry_limit": config["retry_limit"],
        "thresholds": config["thresholds"],
        "config_sha256": digest(config_path),
        "corpus_sha256": digest(CORPUS_PATH),
        "corpus_manifest_sha256": digest(
            ROOT / "data/processed/qasper_external/v1/manifest.json"
        ),
        "index_fingerprint": next(iter(fingerprints)),
        "source_sha256": source_hashes(config_path),
        "cases": cases,
    }
    write_json(FROZEN_CASES, payload, exclusive=True)
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["prepare", "preflight", "run", "seal", "audit", "finalize"]
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_contract(args.config)
    if args.command == "prepare":
        payload = prepare(args.config)
        print(
            json.dumps(
                {"status": "prepared", "cases": len(payload["cases"]), "path": str(FROZEN_CASES)},
                ensure_ascii=False,
            )
        )
        return
    if args.command != "preflight":
        raise SystemExit(f"{args.command} is not implemented yet")
    print(json.dumps({"status": "contract_valid", "cases": len(config["cases"])}))


if __name__ == "__main__":
    main()
