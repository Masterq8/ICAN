"""P3 retrieval-only ablations; allowed gold is consumed only by offline scoring."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from time import perf_counter

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.api.app import load_config
from ican.evaluation.data import digest, load_chunk_registry, load_inputs, read_jsonl
from ican.evaluation.metrics import score_qasper_retrieval, score_swin
from ican.evaluation.runner import append_record, protocol
from ican.retrieval.hybrid import HybridEvidenceSearchService
from ican.retrieval.schema import EvidenceResult, SearchRequest, SearchResponse
from ican.retrieval.scope import eligible, query_config_paths, resolve_family
from ican.retrieval.service import EvidenceSearchService

STRATEGIES = [
    "dense",
    "dense_scoped",
    "bm25",
    "hybrid",
    "hybrid_rerank_raw",
    "hybrid_rerank",
]


def run_identity(root: Path, fixed: dict) -> dict:
    directory, index_manifest = EvidenceSearchService(
        root, load_config(root)
    )._load_index()
    files = sorted((root / "ican/retrieval").glob("*.py")) + [
        root / "ican/api/app.py",
        root / "configs/retrieval/v1.json",
        root / "configs/reranking/v1.json",
        root / "data/catalog/reranker-bge-v2-m3.json",
        root / "scripts/evaluate_retrieval_strategies.py",
    ]
    return {
        "version": "p3-ablation-v1",
        "strategies": STRATEGIES,
        "input_sha256": fixed,
        "source_sha256": {p.relative_to(root).as_posix(): digest(p) for p in files},
        "qa_protocol": protocol(root, ["adapter"]),
        "observed_validation": True,
        "index_fingerprint": directory.name,
        "index_identity": index_manifest["identity"],
        "index_manifest_sha256": digest(directory / "index_manifest.json"),
    }


def validate_records(records: list[dict], cases: list, chunks: dict, fingerprint=None):
    by_key = {}
    case_map = {c.key: c for c in cases}
    fingerprints = set()
    for row in records:
        key = row["key"]
        case = case_map[row["case_key"]]
        if (
            key != case.key + "/" + row["strategy"]
            or row["strategy"] not in STRATEGIES
            or key in by_key
        ):
            raise ValueError("Invalid or duplicate ablation key")
        expected = case.request()
        expected["strategy"] = (
            "hybrid_rerank"
            if row["strategy"] == "hybrid_rerank_raw"
            else row["strategy"]
        )
        if row["request"] != expected or row["case"] != case.record():
            raise ValueError("Ablation request changed")
        response = SearchResponse.model_validate(row["response"])
        fingerprints.add(response.index_fingerprint)
        if fingerprint is not None and response.index_fingerprint != fingerprint:
            raise ValueError("Ablation index differs from immutable manifest")
        parsed = SearchRequest.model_validate(expected)
        if (
            response.query != case.question
            or response.collection != case.collection
            or response.filters != SearchRequest.model_validate(expected).filters
        ):
            raise ValueError("Response differs from query-only request")
        if len({r.chunk_id for r in response.results}) != len(response.results):
            raise ValueError("Duplicate evidence in ablation response")
        family, _ = resolve_family(parsed.query, parsed.collection, parsed.family)
        config_paths = query_config_paths(list(chunks.values()), parsed.query)
        for result in response.results:
            original = chunks[result.chunk_id]
            if (
                result.text != original["text"]
                or result.review_required != original["review_required"]
                or result.source.model_dump()
                != {
                    k: original[k]
                    for k in [
                        "source_id",
                        "source_type",
                        "source_path",
                        "source_version",
                        "location",
                    ]
                }
            ):
                raise ValueError("Ablation evidence differs from fixed corpus")
            # Legacy dense intentionally preserves the unscoped P2 baseline.
            if row["strategy"] != "dense" and not eligible(original, parsed, family):
                raise ValueError("Ablation evidence violated requested scope")
            if (
                row["strategy"] != "dense"
                and original["source_type"] == "config"
                and config_paths is not None
                and original["source_path"] not in config_paths
            ):
                raise ValueError("Ablation evidence violated named YAML scope")
        by_key[key] = row
    if len(fingerprints) > 1:
        raise ValueError("Ablation mixes different index versions")
    return by_key


def raw_ranked_response(
    response: SearchResponse, registry: dict, limit: int
) -> SearchResponse:
    results = []
    for rank, (cid, score) in enumerate(
        response.trace["ranked_candidates"][:limit], start=1
    ):
        c = registry[cid]
        results.append(
            EvidenceResult(
                rank=rank,
                score=score,
                chunk_id=cid,
                text=c["text"],
                review_required=c["review_required"],
                source={
                    k: c[k]
                    for k in [
                        "source_id",
                        "source_type",
                        "source_path",
                        "source_version",
                        "location",
                    ]
                },
            )
        )
    trace = {
        **response.trace,
        "ablation": "without_structural_context",
        "context_added_chunk_ids": [],
        "derived_from": "hybrid_rerank",
    }
    return response.model_copy(update={"results": results, "trace": trace})


def execute(root: Path, directory: Path, phase: str):
    cases, gold, fixed = load_inputs(root)
    identity = run_identity(root, fixed)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8"))["identity"] != identity:
            raise ValueError(
                "Ablation sources/config/input changed; create another run"
            )
    else:
        path.write_text(
            json.dumps(
                {"identity": identity, "cases": [c.record() for c in cases]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    chunks = load_chunk_registry(root)
    output_path = directory / "retrieval.jsonl"
    seal_path = directory / "retrieval-seal.json"
    if (
        seal_path.exists()
        and digest(output_path)
        != json.loads(seal_path.read_text(encoding="utf-8"))["sha256"]
    ):
        raise ValueError("Sealed ablation results changed")
    existing = read_jsonl(output_path) if output_path.exists() else []
    saved = validate_records(existing, cases, chunks, identity["index_fingerprint"])
    service = None
    for case in cases:
        if phase == "calibration" and case.split == "validation":
            continue
        for strategy in [s for s in STRATEGIES if s != "hybrid_rerank_raw"]:
            key = case.key + "/" + strategy
            if key in saved:
                continue
            if seal_path.exists():
                raise ValueError("Sealed result set is incomplete")
            if service is None:
                service = HybridEvidenceSearchService(root, load_config(root))
            request = {**case.request(), "strategy": strategy}
            started = perf_counter()
            response = service.search(SearchRequest.model_validate(request))
            row = {
                "key": key,
                "case_key": case.key,
                "case": case.record(),
                "strategy": strategy,
                "request": request,
                "response": response.model_dump(),
                "elapsed_seconds": perf_counter() - started,
            }
            append_record(output_path, row)
            saved[key] = row
            if strategy == "hybrid_rerank":
                raw = raw_ranked_response(response, chunks, case.request()["limit"])
                extra = {
                    **row,
                    "key": case.key + "/hybrid_rerank_raw",
                    "strategy": "hybrid_rerank_raw",
                    "response": raw.model_dump(),
                    "elapsed_seconds": None,
                    "timing_note": "derived ranking from the same scoring pass; no extra model dispatch",
                }
                append_record(output_path, extra)
                saved[extra["key"]] = extra
            print(f"retrieved {key}", flush=True)
    # An interrupted append after rerank but before derived raw may be restored offline.
    for case in cases:
        parent = saved.get(case.key + "/hybrid_rerank")
        key = case.key + "/hybrid_rerank_raw"
        if parent and key not in saved:
            if seal_path.exists():
                raise ValueError("Sealed result set is missing derived ranking")
            row = {
                **parent,
                "key": key,
                "strategy": "hybrid_rerank_raw",
                "response": raw_ranked_response(
                    SearchResponse.model_validate(parent["response"]), chunks, 8
                ).model_dump(),
                "elapsed_seconds": None,
                "timing_note": "derived ranking; no extra model dispatch",
            }
            append_record(output_path, row)
            saved[key] = row
    validate_records(list(saved.values()), cases, chunks, identity["index_fingerprint"])
    complete = len(saved) == len(cases) * len(STRATEGIES)
    if complete and not seal_path.exists():
        seal_path.write_text(
            json.dumps({"sha256": digest(output_path), "n": len(saved)}, indent=2),
            encoding="utf-8",
        )
    corpus = {
        r["unit_id"]: r["text"]
        for split in ["train", "validation"]
        for r in read_jsonl(
            root / f"data/processed/qasper_external/v1/{split}_corpus.jsonl"
        )
    }
    specs = {
        r["id"]: r
        for r in json.loads(
            (root / "data/eval/swin_evidence.json").read_text(encoding="utf-8")
        )["evidence"]
    }
    grouped = defaultdict(list)
    details = []
    for row in saved.values():
        for k in [1, 3, 5, 8]:
            selected = [chunks[r["chunk_id"]] for r in row["response"]["results"][:k]]
            score = (
                score_swin(gold[row["case_key"]]["required_evidence"], specs, selected)
                if row["case"]["dataset"] == "swin"
                else score_qasper_retrieval(gold[row["case_key"]], selected, corpus)
            )
            grouped[
                (row["case"]["dataset"], row["case"]["split"], row["strategy"], k)
            ].append(score)
            details.append({"key": row["key"], "k": k, **score})
    results = []
    for (dataset, split, strategy, k), rows in sorted(grouped.items()):
        fields = (
            ["locator_recall", "repository_complete_recall"]
            if dataset == "swin"
            else ["unit_hit_recall", "complete_unit_recall"]
        )
        result = {
            "dataset": dataset,
            "split": split,
            "strategy": strategy,
            "k": k,
            "n": len(rows),
        }
        for field in fields:
            applicable = [r[field] for r in rows if r[field] is not None]
            result[field] = mean(applicable) if applicable else None
            result[field + "_n"] = len(applicable)
        results.append(result)
    summary = {
        "identity": identity,
        "complete": complete,
        "recorded_n": len(saved),
        "expected_n": len(cases) * len(STRATEGIES),
        "metrics": results,
        "details": details,
        "generation_calls": 0,
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "complete": complete,
                "records": len(saved),
                "top8": [r for r in results if r["k"] == 8],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=["calibration", "all"], default="calibration"
    )
    args = parser.parse_args()
    args.run_dir.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(args.run_dir.parent / f".{args.run_dir.name}.lock", timeout=0):
        execute(ROOT, args.run_dir, args.phase)
