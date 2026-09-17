from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from ican.evaluation.data import digest, load_chunk_registry, load_inputs, read_jsonl
from ican.evaluation.metrics import (
    answer_for_official_score,
    qasper_references,
    score_qasper_retrieval,
    score_swin,
    unit_coverage,
)
from ican.evaluation.runner import validate_snapshot
from third_party.qasper.evaluator import evaluate


def summarize(root: Path, directory: Path) -> dict:
    cases, gold, fixed = load_inputs(root)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if fixed != manifest["input_sha256"]:
        raise ValueError("Report inputs differ from run snapshot")
    chunks = load_chunk_registry(root)
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
    retrieval = list(validate_snapshot(root, directory, cases, manifest).values())
    details, grouped = [], defaultdict(list)
    for record in retrieval:
        key = record["key"]
        dataset, split = record["case"]["dataset"], record["case"]["split"]
        for k in manifest["protocol"]["k"]:
            selected = [
                chunks[r["chunk_id"]] for r in record["response"]["results"][:k]
            ]
            score = (
                score_swin(gold[key]["required_evidence"], specs, selected)
                if dataset == "swin"
                else score_qasper_retrieval(gold[key], selected, corpus)
            )
            details.append({"key": key, "k": k, **score})
            grouped[(dataset, split, k)].append(score)
    retrieval_summary = []
    for (dataset, split, k), values in grouped.items():
        fields = (
            ["locator_recall", "repository_complete_recall"]
            if dataset == "swin"
            else ["unit_hit_recall", "complete_unit_recall"]
        )
        row = {"dataset": dataset, "split": split, "k": k, "n": len(values)}
        for field in fields:
            valid = [v[field] for v in values if v[field] is not None]
            row[field] = mean(valid) if valid else None
            row[field + "_n"] = len(valid)
        row["complete_set_rate"] = mean(
            bool(v.get("locator_set_complete", v.get("complete_evidence_set")))
            for v in values
        )
        retrieval_summary.append(row)
    journal_path = directory / "journal.jsonl"
    journal = read_jsonl(journal_path) if journal_path.exists() else []
    completed = {r["key"]: r for r in journal if r["event"] in ["completed", "error"]}
    started_keys = {r["key"] for r in journal if r["event"] == "started"}
    generation_summary = []
    for dataset, split in [
        ("qasper", "train"),
        ("swin", "dev"),
        ("qasper", "validation"),
    ]:
        selected_cases = [c for c in cases if c.dataset == dataset and c.split == split]
        for variant in manifest["protocol"]["variants"]:
            records = [
                completed[c.key + "/" + variant]
                for c in selected_cases
                if c.key + "/" + variant in completed
            ]
            attempted_keys = {
                c.key + "/" + variant for c in selected_cases
            } & started_keys
            unfinished = attempted_keys - completed.keys()
            valid_citations = sum(r.get("citation_valid", False) for r in records)
            row = {
                "dataset": dataset,
                "split": split,
                "variant": variant,
                "expected_n": len(selected_cases),
                "recorded_n": len(records),
                "attempted_n": len(attempted_keys),
                "unfinished_started_n": len(unfinished),
                "failed_or_unfinished_n": sum(r["event"] == "error" for r in records)
                + len(unfinished),
                "error_n": sum(r["event"] == "error" for r in records),
                "citation_valid_rate": valid_citations / len(attempted_keys)
                if attempted_keys
                else None,
                "citation_valid_rate_all_cases": valid_citations / len(selected_cases)
                if attempted_keys
                else None,
                "usage_missing_n": len(unfinished)
                + sum("prompt_tokens" not in r["usage"] for r in records),
                "abstention_n": sum(r.get("abstained", False) for r in records),
                "review_required_n": sum(
                    r.get("review_required", False) for r in records
                ),
                "prompt_tokens_reported": sum(
                    r["usage"].get("prompt_tokens", 0) for r in records
                ),
                "completion_tokens_reported": sum(
                    r["usage"].get("completion_tokens", 0) for r in records
                ),
                "request_seconds_median": median(r["elapsed_seconds"] for r in records)
                if records
                else None,
                "cost_usd": None,
            }
            if dataset == "qasper":
                refs = {c.id: qasper_references(gold[c.key]) for c in selected_cases}
                predictions, full_predictions = {}, {}
                for case in selected_cases:
                    record = completed.get(case.key + "/" + variant)
                    if record is None or record["event"] == "error":
                        continue  # Official evaluator assigns missing predictions zero.
                    cited = [
                        chunks[c["evidence"]["chunk_id"]] for c in record["citations"]
                    ]
                    hit, full = unit_coverage(cited, corpus)

                    def unit_texts(units):
                        return [
                            ("FLOAT SELECTED: " if ":caption:" in unit else "")
                            + corpus[unit]
                            for unit in sorted(units)
                        ]

                    answer = answer_for_official_score(
                        record["raw_answer"], record["abstained"]
                    )
                    predictions[case.id] = {
                        "answer": answer,
                        "evidence": unit_texts(hit),
                    }
                    full_predictions[case.id] = {
                        "answer": answer,
                        "evidence": unit_texts(full),
                    }
                row["official_metrics"] = (
                    evaluate(refs, predictions) if attempted_keys else None
                )
                row["complete_paragraph_evidence_f1"] = (
                    evaluate(refs, full_predictions)["Evidence F1"]
                    if attempted_keys
                    else None
                )
            generation_summary.append(row)
    audits_path = directory / "semantic-audit.jsonl"
    audits = read_jsonl(audits_path) if audits_path.exists() else []
    output = {
        "run_manifest": manifest,
        "retrieval": retrieval_summary,
        "retrieval_details": details,
        "generation": generation_summary,
        "started_calls": sum(r["event"] == "started" for r in journal),
        "completed_or_error_n": len(completed),
        "unfinished_started_n": len(started_keys - completed.keys()),
        "generation_calls_reported": sum(
            r["usage"]["generation_calls"] for r in completed.values()
        ),
        "semantic_audit_n": len(audits),
        "semantic_audits": audits,
        "index_fingerprints": sorted(
            {r["response"]["index_fingerprint"] for r in retrieval}
        ),
        "evaluator_sha256": digest(root / "third_party/qasper/evaluator.py"),
        "retrieval_seconds_median": median(r["elapsed_seconds"] for r in retrieval)
        if retrieval
        else None,
        "incomplete": len(completed)
        != len(cases) * len(manifest["protocol"]["variants"]),
    }
    (directory / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output
