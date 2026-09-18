"""Bind explicit assistant reviews to one immutable, completed evaluation run.

Offline only: this script does not grade answers or call a model. Reviewers supply
the judgments; hashes prevent replaying them against newly generated answers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ican.evaluation.data import digest, load_inputs, read_jsonl
from ican.evaluation.report import summarize
from ican.evaluation.runner import validate_snapshot


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_completed_run(journal: list[dict], expected_keys: set[str]) -> dict:
    starts = [r["key"] for r in journal if r["event"] == "started"]
    terminals = [r for r in journal if r["event"] == "completed"]
    terminal_keys = [r["key"] for r in terminals]
    if (
        len(journal) != 2 * len(expected_keys)
        or len(starts) != len(set(starts))
        or set(starts) != expected_keys
        or len(terminal_keys) != len(set(terminal_keys))
        or set(terminal_keys) != expected_keys
        or any(r["usage"].get("generation_calls") != 1 for r in terminals)
    ):
        raise ValueError(
            "Audit requires unique paired starts and single-call completions"
        )
    seen = set()
    for row in journal:
        if row["event"] == "started":
            seen.add(row["key"])
        elif row["event"] != "completed" or row["key"] not in seen:
            raise ValueError("Completion must follow its own started record")
    return {r["key"]: r for r in terminals}


def validate_reviews(reviews: list[dict], completed: dict, gold: dict) -> None:
    keys = [r["case_key"] + "/" + r["variant"] for r in reviews]
    if len(keys) != len(set(keys)) or set(keys) != set(completed):
        raise ValueError("Reviews must cover each completed answer exactly once")
    for row in reviews:
        if row["answer_judgment"] not in {
            "full",
            "partial",
            "incorrect",
            "abstained",
            "ambiguous_reference",
        }:
            raise ValueError("Invalid answer judgment")
        if row["citation_support"] not in {
            "supported",
            "partial",
            "unsupported",
            "not_applicable",
        }:
            raise ValueError("Invalid citation support judgment")
        if not row["reason"].strip() or not row["citation_reason"].strip():
            raise ValueError("Every judgment needs an explicit reason")
        if type(row["semantic_abstained"]) is not bool:
            raise ValueError("Semantic abstention must be boolean")
        if (
            row["semantic_status_correct"] is not None
            and type(row["semantic_status_correct"]) is not bool
        ):
            raise ValueError("Status judgment must be boolean or null")
        if row.get("reviewer_type", "assistant") != "assistant":
            raise ValueError("This acceptance run contains assistant reviews only")
        if row["case_key"].startswith("swin/"):
            scores = row["grading_point_scores"]
            if len(scores) != len(gold[row["case_key"]]["grading_points"]) or any(
                type(s) is not int or s not in (0, 1) for s in scores
            ):
                raise ValueError("Swin scores must match the fixed rubric")


def finalize(
    root: Path,
    directory: Path,
    review_directory: Path,
    binding_name="p26-audit-manifest.json",
) -> dict:
    binding = json.loads((review_directory / binding_name).read_text(encoding="utf-8"))
    journal_path = directory / "journal.jsonl"
    if digest(journal_path) != binding["journal_sha256"]:
        raise ValueError("Judgments belong to a different generation journal")
    cases, gold, fixed = load_inputs(root)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if fixed != binding["input_sha256"] or fixed != manifest["input_sha256"]:
        raise ValueError("Review reference inputs have changed")
    if digest(directory / "retrieval.jsonl") != binding["retrieval_sha256"]:
        raise ValueError("Judgments belong to a different retrieval snapshot")
    validate_snapshot(root, directory, cases, manifest)
    reviews = []
    for name, expected in binding["review_files_sha256"].items():
        if digest(review_directory / name) != expected:
            raise ValueError("Review file changed; create a new audit revision")
        reviews.extend(read_jsonl(review_directory / name))
    journal = read_jsonl(journal_path)
    expected_keys = {
        c.key + "/" + variant
        for c in cases
        for variant in manifest["protocol"]["variants"]
    }
    completed = validate_completed_run(journal, expected_keys)
    validate_reviews(reviews, completed, gold)
    audits = []
    for row in reviews:
        key = row["case_key"] + "/" + row["variant"]
        record = completed[key]
        audits.append(
            {
                **row,
                "key": key,
                "reviewer_type": "assistant",
                "rubric_version": "p26-semantic-v1",
                "raw_answer_sha256": text_digest(record["raw_answer"]),
                "cited_evidence_sha256": text_digest(
                    json.dumps(record["citations"], sort_keys=True, ensure_ascii=False)
                ),
                "recorded_abstained": record["abstained"],
                "journal_sha256": binding["journal_sha256"],
            }
        )
    audits.sort(key=lambda r: r["key"])
    (directory / "semantic-audit.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in audits),
        encoding="utf-8",
    )
    summary = summarize(root, directory)
    grouped = defaultdict(list)
    for row in audits:
        dataset, split, _ = row["case_key"].split("/")
        grouped[(dataset, split, row["variant"])].append(row)
    results = []
    for (dataset, split, variant), rows in grouped.items():
        statuses = [
            r["semantic_status_correct"]
            for r in rows
            if r["semantic_status_correct"] is not None
        ]
        applicable = [r for r in rows if r["citation_support"] != "not_applicable"]
        result = {
            "dataset": dataset,
            "split": split,
            "variant": variant,
            "n": len(rows),
            "answer_judgments": dict(Counter(r["answer_judgment"] for r in rows)),
            "citation_support_judgments": dict(
                Counter(r["citation_support"] for r in rows)
            ),
            "fully_supported_answer_n": sum(
                r["citation_support"] == "supported" for r in applicable
            ),
            "citation_support_applicable_n": len(applicable),
            "semantic_abstention_n": sum(r["semantic_abstained"] for r in rows),
            "abstention_discrepancy_keys": [
                r["key"]
                for r in rows
                if r["semantic_abstained"] != r["recorded_abstained"]
            ],
            "semantic_status_scored_n": len(statuses),
            "semantic_status_correct_n": sum(statuses),
            "semantic_status_accuracy_scored_subset": mean(statuses)
            if statuses
            else None,
        }
        if dataset == "swin":
            result["grading_points_covered"] = sum(
                sum(r["grading_point_scores"]) for r in rows
            )
            result["grading_points_total"] = sum(
                len(r["grading_point_scores"]) for r in rows
            )
            result["grading_coverage_macro"] = mean(
                sum(r["grading_point_scores"]) / len(r["grading_point_scores"])
                for r in rows
            )
        results.append(result)
    usage = summary["generation"]
    prompt_tokens = sum(r["prompt_tokens_reported"] for r in usage)
    output_tokens = sum(r["completion_tokens_reported"] for r in usage)
    output = {
        "reviewer_type": "assistant",
        "human_reviewed": False,
        "audit_manifest": binding,
        "started_calls": summary["started_calls"],
        "generation_calls_reported": summary["generation_calls_reported"],
        "semantic_audit_n": len(audits),
        "semantic_results": results,
        "retrieval": summary["retrieval"],
        "generation": usage,
        "billing": {
            "prompt_tokens_reported": prompt_tokens,
            "completion_tokens_reported": output_tokens,
            "actual_cost_usd": None,
            "estimated_usd_peak_all_input_cache_miss": (
                prompt_tokens * 0.30 + output_tokens * 1.20
            )
            / 1_000_000,
            "price_verified_date": "2026-09-17",
            "price_source": "https://api-docs.deepseek.com/quick_start/pricing/",
            "assumption": "USD per million: input0.30, output1.20; actual cache/time discounts unknown",
            "billing_csv_status": "supplied temporary paths expired; actual receipt unavailable",
        },
    }
    (directory / "acceptance-summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, default=ROOT / "docs/evaluation")
    parser.add_argument("--audit-manifest", default="p26-audit-manifest.json")
    args = parser.parse_args()
    from filelock import FileLock

    with FileLock(args.run_dir.parent / f".{args.run_dir.name}.lock", timeout=0):
        result = finalize(ROOT, args.run_dir, args.review_dir, args.audit_manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
