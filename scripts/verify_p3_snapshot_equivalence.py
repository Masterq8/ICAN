"""Compare prepared PaperQA2 inputs after a retrieval-only functional fix.

Offline verification: this neither generates answers nor transfers judgments to
new answers. The original answer journal and its audit remain bound to v1.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.data import digest, load_chunk_registry, load_inputs, read_jsonl
from ican.evaluation.runner import prepare_variant, validate_snapshot
from ican.qa.schema import QAConfig
from ican.retrieval.schema import SearchResponse
from scripts.evaluate_retrieval_strategies import (
    STRATEGIES,
    run_identity,
    validate_records,
)


async def verify():
    original = ROOT / "data/processed/evaluation/p3-qa-v1"
    latest = ROOT / "data/processed/evaluation/p3-final-v3"
    cases, _, fixed = load_inputs(ROOT)
    old_manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    old = validate_snapshot(ROOT, original, cases, old_manifest)
    manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    seal = json.loads((latest / "retrieval-seal.json").read_text(encoding="utf-8"))
    if manifest["identity"] != run_identity(ROOT, fixed):
        raise ValueError("Latest retrieval identity changed")
    if seal["sha256"] != digest(latest / "retrieval.jsonl"):
        raise ValueError("Latest retrieval seal changed")
    records = read_jsonl(latest / "retrieval.jsonl")
    validate_records(
        records,
        cases,
        load_chunk_registry(ROOT),
        manifest["identity"]["index_fingerprint"],
    )
    if len(records) != len(cases) * len(STRATEGIES):
        raise ValueError("Latest retrieval is incomplete")
    current = {r["case_key"]: r for r in records if r["strategy"] == "hybrid_rerank"}
    config = QAConfig.model_validate_json(
        (ROOT / "configs/qa/v1.json").read_text(encoding="utf-8")
    )
    comparisons = []
    for case in cases:
        inputs = []
        for response in (old[case.key]["response"], current[case.key]["response"]):
            search = SearchResponse.model_validate(response)
            prepared, serialized = await prepare_variant(
                case.question, search.results, config, "adapter"
            )
            payload = {
                "question": case.question,
                "context": serialized,
                "system": prepared.settings.prompts.system,
                "qa": prepared.settings.prompts.qa,
                "config": config.model_dump(),
                "included": list(prepared.registry),
                "dropped": prepared.dropped_chunk_ids,
            }
            inputs.append(
                hashlib.sha256(
                    json.dumps(payload, sort_keys=True, ensure_ascii=False).encode(
                        "utf-8"
                    )
                ).hexdigest()
            )
        comparisons.append(
            {
                "case_key": case.key,
                "original_input_sha256": inputs[0],
                "latest_input_sha256": inputs[1],
                "equal": inputs[0] == inputs[1],
            }
        )
    result = {
        "original_run": "p3-qa-v1",
        "latest_retrieval_run": "p3-final-v3",
        "original_retrieval_sha256": digest(original / "retrieval.jsonl"),
        "original_journal_sha256": digest(original / "journal.jsonl"),
        "latest_retrieval_seal": seal,
        "cases": len(cases),
        "equal_prepared_input_n": sum(r["equal"] for r in comparisons),
        "generation_calls": 0,
        "bound_generation_identity": json.loads(
            (original / "generation-identity.json").read_text(encoding="utf-8")
        ),
        "note": "Inputs compared under the same pinned adapter and generation identity; no new answer or semantic judgment is created.",
        "comparisons": comparisons,
    }
    (ROOT / "docs/evaluation/p3-input-equivalence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": result["cases"],
                "equal_prepared_input_n": result["equal_prepared_input_n"],
                "generation_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(verify())
