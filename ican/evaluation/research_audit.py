"""Verify the sealed one-call run before reading reviewer labels."""

import hashlib
import json
import subprocess
from pathlib import Path


def verify_audit_inputs(root: Path, run_dir: Path, manifest: dict, seal: dict):
    for relative, expected in seal["artifact_sha256"].items():
        path = (run_dir / relative).resolve()
        if not path.is_relative_to(run_dir.resolve()):
            raise ValueError("Audit artifact is outside run directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Sealed artifact changed: {relative}")
    required = {"manifest.json", "paid-journal.jsonl"}
    for key in manifest["cases"]:
        required |= {f"{key}.started.json", f"{key}.result.json"}
        result = json.loads(
            (run_dir / f"{key}.result.json").read_text(encoding="utf-8")
        )
        if result.get("trace"):
            required.add("traces/" + result["trace"])
    if not required <= seal["artifact_sha256"].keys():
        raise ValueError("Incomplete run seal")
    for relative, expected in manifest["source_sha256"].items():
        original = subprocess.check_output(
            ["git", "show", f"{seal['run_source_commit']}:{relative}"], cwd=root
        )
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError(f"Frozen source commit mismatch: {relative}")
    rows = [
        json.loads(line)
        for line in (run_dir / "paid-journal.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    starts = {row["call_id"]: row for row in rows if row["event"] == "started"}
    ends = {row["call_id"]: row for row in rows if row["event"] != "started"}
    if (
        len(starts) != len(manifest["cases"])
        or len(rows) != 2 * len(starts)
        or starts.keys() != ends.keys()
    ):
        raise ValueError("Journal must contain one completed reservation per case")
    used = set()
    for key, case in manifest["cases"].items():
        result = json.loads(
            (run_dir / f"{key}.result.json").read_text(encoding="utf-8")
        )
        trace = json.loads(
            (run_dir / "traces" / result["trace"]).read_text(encoding="utf-8")
        )
        if len(trace["model_records"]) != 1:
            raise ValueError("Expected one model record per case")
        record = trace["model_records"][0]
        call_id = record["call_id"]
        if call_id in used or call_id not in starts:
            raise ValueError("Reused or unknown paid call")
        used.add(call_id)
        if (
            starts[call_id]["task_id"] != trace["task_id"]
            or starts[call_id]["model"] != manifest["model"]
            or record["usage"] != ends[call_id]["usage"]
            or trace["request"] != case["request"]
        ):
            raise ValueError("Trace/journal identity mismatch")
    return {
        "paid_calls": len(starts),
        "prompt_tokens": sum(
            (row.get("usage") or {}).get("prompt_tokens", 0) for row in ends.values()
        ),
        "completion_tokens": sum(
            (row.get("usage") or {}).get("completion_tokens", 0)
            for row in ends.values()
        ),
        "actual_cost_usd": None,
    }
