from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ican.evaluation.data import digest, load_chunk_registry, load_inputs, read_jsonl
from ican.qa.paperqa_adapter import DisabledModel, prepare_evidence
from ican.qa.prompts import INSUFFICIENT
from ican.qa.runtime import ModelTimeout, ModelUnavailable, OpenAICompatibleModel
from ican.qa.schema import QAConfig
from ican.qa.service import CITATION_PATTERN, CapturedAnswerModel
from ican.retrieval.schema import SearchRequest, SearchResponse


def append_record(path: Path, record: dict):
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class CallJournal:
    """Single-process writer. A started request never automatically dispatches again."""

    def __init__(self, path: Path, max_calls: int):
        self.path = path
        self.max_calls = max_calls
        records = read_jsonl(path) if path.exists() else []
        self.started = {r["key"] for r in records if r["event"] == "started"}

    def reserve(self, key: str) -> bool:
        if key in self.started:
            return False
        if len(self.started) >= self.max_calls:
            raise RuntimeError("Generation call budget exhausted")
        append_record(
            self.path,
            {
                "event": "started",
                "key": key,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.started.add(key)
        return True


async def prepare_variant(question, evidence, config, variant):
    from paperqa import Settings

    prepared = await prepare_evidence(question, evidence, config)
    if variant == "adapter":
        prepared.settings.prompts.system = prepared.settings.prompts.system.replace(
            "使用中文", "使用问题的语言"
        )
    elif variant == "paperqa-default":
        prepared.settings = Settings(
            parsing={"defer_embedding": True},
            answer={"get_evidence_if_no_contexts": False},
        )
    else:
        raise ValueError("Unknown evaluation variant")
    serialized = await prepared.settings.context_serializer(
        contexts=prepared.session.contexts, question=question, pre_str=None
    )
    sent = set(CITATION_PATTERN.findall(serialized)) & prepared.registry.keys()
    unused = [e.chunk_id for cid, e in prepared.registry.items() if cid not in sent]
    prepared.registry = {
        cid: item for cid, item in prepared.registry.items() if cid in sent
    }
    prepared.session.contexts = [c for c in prepared.session.contexts if c.id in sent]
    prepared.dropped_chunk_ids.extend(unused)
    return prepared, serialized


def protocol(root: Path, variants: list[str]) -> dict:
    from paperqa import Settings

    from ican.qa.prompts import QA, SYSTEM

    files = [
        *sorted((root / "ican/evaluation").glob("*.py")),
        *sorted((root / "ican/qa").glob("*.py")),
        root / "third_party/qasper/evaluator.py",
        root / "configs/qa/v1.json",
        root / "configs/indexing/v1.json",
        root / "scripts/evaluate_baseline.py",
    ]
    return {
        "variants": variants,
        "k": [1, 3, 5, 8],
        "query_limit": 8,
        "adapter_prompt_version": "eval-adapter-v2-question-language-v1",
        "adapter_prompt_sha256": hashlib.sha256(
            (SYSTEM.replace("使用中文", "使用问题的语言") + QA).encode()
        ).hexdigest(),
        "upstream_settings": Settings().model_dump(mode="json"),
        "code_sha256": {p.relative_to(root).as_posix(): digest(p) for p in files},
    }


def validate_snapshot(root: Path, directory: Path, cases, manifest: dict) -> dict:
    path = directory / "retrieval.jsonl"
    if digest(path) != manifest.get("retrieval_sha256"):
        raise ValueError("Retrieval snapshot changed or has not been sealed")
    records = read_jsonl(path)
    snapshots = {r["key"]: r for r in records}
    if len(snapshots) != len(records) or set(snapshots) != {c.key for c in cases}:
        raise ValueError("Retrieval snapshot is incomplete or has duplicate keys")
    registry = load_chunk_registry(root)
    fingerprints = set()
    for case in cases:
        record = snapshots[case.key]
        search = SearchResponse.model_validate(record["response"])
        request = SearchRequest.model_validate(case.request())
        if (
            record["case"] != case.record()
            or search.query != request.query
            or search.collection != request.collection
            or search.filters != request.filters
        ):
            raise ValueError("Snapshot request differs from query-only case")
        fingerprints.add(search.index_fingerprint)
        for result in search.results:
            chunk = registry[result.chunk_id]
            expected_source = {
                key: chunk[key]
                for key in [
                    "source_id",
                    "source_type",
                    "source_path",
                    "source_version",
                    "location",
                ]
            }
            if (
                result.text != chunk["text"]
                or result.review_required != chunk["review_required"]
                or result.source.model_dump() != expected_source
            ):
                raise ValueError("Snapshot evidence differs from fixed chunk registry")
    if len(fingerprints) != 1:
        raise ValueError("Snapshot mixes different index versions")
    return snapshots


def reuse_retrieval(root: Path, directory: Path, source: Path, variants: list[str]):
    """Reuse preflight ranking after checking unchanged questions, inputs and chunks."""
    cases, _, inputs = load_inputs(root)
    initial = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (
        initial.get("retrieval_sha256")
        and digest(source / "retrieval.jsonl") != initial["retrieval_sha256"]
    ):
        raise ValueError("Sealed source snapshot changed")
    if (
        initial["cases"] != [c.record() for c in cases]
        or any(inputs.get(p) != h for p, h in initial["input_sha256"].items())
        or initial["protocol"]["query_limit"] != 8
    ):
        raise ValueError("Source snapshot inputs differ")
    if directory.exists():
        raise ValueError("Reuse destination must be a new directory")
    directory.mkdir(parents=True)
    path = directory / "retrieval.jsonl"
    path.write_bytes((source / "retrieval.jsonl").read_bytes())
    manifest = {
        "protocol": protocol(root, variants),
        "input_sha256": inputs,
        "cases": [c.record() for c in cases],
        "retrieval_sha256": digest(path),
        "retrieval_provenance": initial,
    }
    validate_snapshot(root, directory, cases, manifest)
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def retrieve(root: Path, directory: Path, service, variants: list[str]):
    cases, _, inputs = load_inputs(root)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest = {
        "protocol": protocol(root, variants),
        "input_sha256": inputs,
        "cases": [c.record() for c in cases],
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("retrieval_sha256"):
            validate_snapshot(root, directory, cases, existing)
            return  # A sealed ranking is immutable, including after generation starts.
        if {k: existing[k] for k in manifest} != manifest:
            raise ValueError(
                "Existing run protocol differs; create a new run directory"
            )
    else:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    path = directory / "retrieval.jsonl"
    saved = {r["key"] for r in read_jsonl(path)} if path.exists() else set()
    for case in cases:
        if case.key in saved:
            continue
        started = perf_counter()
        result = service.search(SearchRequest.model_validate(case.request()))
        append_record(
            path,
            {
                "key": case.key,
                "case": case.record(),
                "response": result.model_dump(),
                "elapsed_seconds": perf_counter() - started,
            },
        )
        print(f"Retrieved {case.key}", flush=True)
    manifest["retrieval_sha256"] = digest(path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    validate_snapshot(root, directory, cases, manifest)


async def generate(root: Path, directory: Path, max_calls: int, model_factory=None):
    cases, _, inputs = load_inputs(root)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    variants = manifest["protocol"]["variants"]
    if (
        manifest["protocol"] != protocol(root, variants)
        or manifest["input_sha256"] != inputs
    ):
        raise ValueError("Run inputs or protocol changed; create a new directory")
    config = QAConfig.model_validate_json(
        (root / "configs/qa/v1.json").read_text(encoding="utf-8")
    )
    factory = model_factory or (lambda: OpenAICompatibleModel(root, config))
    identity_model = factory()
    identity = {
        "model": identity_model.name,
        "base_url": getattr(identity_model, "base_url", "offline"),
    }
    identity_path = directory / "generation-identity.json"
    if identity_path.exists():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise ValueError("Generation model changed; create a new run directory")
    else:
        identity_path.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    snapshots = validate_snapshot(root, directory, cases, manifest)
    journal = CallJournal(directory / "journal.jsonl", max_calls)
    for case in cases:
        search = SearchResponse.model_validate(snapshots[case.key]["response"])
        for variant in variants:
            key = case.key + "/" + variant
            if key in journal.started:
                continue
            prepared, _ = await prepare_variant(
                case.question, search.results, config, variant
            )
            if not journal.reserve(key):
                continue
            started = perf_counter()
            record = {
                "event": "completed",
                "key": key,
                "case_key": case.key,
                "variant": variant,
                "model": identity["model"],
                "index_fingerprint": search.index_fingerprint,
                "included_chunk_ids": [e.chunk_id for e in prepared.registry.values()],
                "dropped_chunk_ids": prepared.dropped_chunk_ids,
            }
            captured = CapturedAnswerModel(factory())
            try:
                session = await asyncio.wait_for(
                    prepared.docs.aquery(
                        prepared.session,
                        settings=prepared.settings,
                        llm_model=captured,
                        summary_llm_model=DisabledModel(),
                        embedding_model=DisabledModel(),
                    ),
                    timeout=config.timeout_seconds,
                )
                raw = captured.raw_answer
                ids = list(dict.fromkeys(CITATION_PATTERN.findall(raw)))
                valid = [cid for cid in ids if cid in prepared.registry]
                invalid = [cid for cid in ids if cid not in prepared.registry]
                abstained = INSUFFICIENT in raw or bool(
                    re.match(
                        r"\s*(?:I cannot answer|I can't answer)", raw, re.IGNORECASE
                    )
                )
                citations = [
                    {"context_id": cid, "evidence": prepared.registry[cid].model_dump()}
                    for cid in valid
                ]
                counts = list(session.token_counts.values())
                record.update(
                    raw_answer=raw,
                    citations=citations,
                    invalid_citation_ids=invalid,
                    abstained=abstained,
                    citation_valid=bool(valid) and not invalid,
                    review_required=any(
                        prepared.registry[cid].review_required for cid in valid
                    ),
                    usage={
                        "generation_calls": captured.calls,
                        "prompt_tokens": sum(x[0] for x in counts),
                        "completion_tokens": sum(x[1] for x in counts),
                        "cost_usd": None,
                    },
                )
            except (ModelUnavailable, ModelTimeout, TimeoutError):
                record.update(
                    event="error",
                    error="Generation unavailable or timed out",
                    usage={"generation_calls": captured.calls, "cost_usd": None},
                )
            record["elapsed_seconds"] = perf_counter() - started
            append_record(directory / "journal.jsonl", record)
            print(f"{record['event']} {key}", flush=True)
