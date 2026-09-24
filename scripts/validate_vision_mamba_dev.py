"""Validate the source bindings of the Vision Mamba development set.

The gold files are deliberately outside every retrieval input. This script reads
the fixed paper, repository, parsed pages, and current v2 chunks; it never runs
repository code or calls a model.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = "data/raw/papers/vision_mamba_2401.09417.pdf"
MODEL = "data/raw/repositories/Vim/vim/models_mamba.py"
SSM = "data/raw/repositories/Vim/mamba-1p1p1/mamba_ssm/modules/mamba_simple.py"
ALLOWED_SOURCES = {PAPER, MODEL, SSM}
PAPER_VERSION = "arXiv:2401.09417"
REPO_COMMIT = "dd0358ad1e42701f22afbefa0717cc8825cf9f45"
PAPER_SHA256 = "15c3ccf7340a412e6ce408526c03a67e412d9bb4958e6c0bfe310394b6337444"
CHUNKS_SHA256 = "56d921f77fa35f9527166dbf1672caaa66e5fd07fd46bb68705a46dc85c921db"
CHUNKS = "data/processed/vision_mamba/chunks/v2/chunks.jsonl"
PARSED = "data/processed/vision_mamba/v1/parsed_units.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def validate(
    root: Path,
    *,
    evidence_data: dict | None = None,
    questions: list[dict] | None = None,
) -> list[str]:
    """Return source-binding and question-integrity errors; an empty list passes."""
    errors: list[str] = []
    if evidence_data is None:
        evidence_data = json.loads(
            (root / "data/eval/vision_mamba_evidence.json").read_text(encoding="utf-8")
        )
    if questions is None:
        questions = _load_jsonl(root / "data/eval/vision_mamba_dev.jsonl")

    paper = root / PAPER
    chunk_path = root / CHUNKS
    if (
        _sha256(paper) != PAPER_SHA256
        or evidence_data.get("pdf_sha256") != PAPER_SHA256
    ):
        errors.append("Vim PDF SHA-256 differs from the evidence map")
    if (
        _sha256(chunk_path) != CHUNKS_SHA256
        or evidence_data.get("chunks_sha256") != CHUNKS_SHA256
    ):
        errors.append("Vim v2 chunks SHA-256 differs from the evidence map")
    head = subprocess.run(
        ["git", "-C", str(root / "data/raw/repositories/Vim"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if (
        head.returncode
        or head.stdout.strip() != REPO_COMMIT
        or evidence_data.get("repo_commit") != REPO_COMMIT
    ):
        errors.append("Vim repository HEAD differs from the evidence map")
    for source_path in (MODEL, SSM):
        relative = Path(source_path).relative_to("data/raw/repositories/Vim").as_posix()
        committed = subprocess.run(
            [
                "git",
                "-C",
                str(root / "data/raw/repositories/Vim"),
                "show",
                f"{REPO_COMMIT}:{relative}",
            ],
            capture_output=True,
            check=False,
        )
        worktree_content = (root / source_path).read_bytes().replace(b"\r\n", b"\n")
        committed_content = committed.stdout.replace(b"\r\n", b"\n")
        if committed.returncode or worktree_content != committed_content:
            errors.append(f"{source_path}: worktree source differs from pinned commit")

    chunks = {row["chunk_id"]: row for row in _load_jsonl(chunk_path)}
    paper_pages = {
        row["page"]: row["text"]
        for row in _load_jsonl(root / PARSED)
        if row.get("source_type") == "paper" and row.get("path") == PAPER
    }
    evidence_by_id: dict[str, dict] = {}
    for item in evidence_data.get("evidence", []):
        evidence_id = item.get("id", "<missing id>")
        if evidence_id in evidence_by_id:
            errors.append(f"duplicate evidence id: {evidence_id}")
        evidence_by_id[evidence_id] = item
        source_path = item.get("source_path")
        if source_path not in ALLOWED_SOURCES:
            errors.append(f"{evidence_id}: source_path is outside fixed Vim-Ti sources")
            continue
        chunk = chunks.get(item.get("chunk_id"))
        if chunk is None:
            errors.append(f"{evidence_id}: chunk_id is absent from Vim v2 chunks")
            continue
        if chunk.get("source_path") != source_path:
            errors.append(f"{evidence_id}: chunk source_path mismatch")
        expected_type = "paper" if source_path == PAPER else "code"
        expected_version = PAPER_VERSION if source_path == PAPER else REPO_COMMIT
        if (
            item.get("source_type") != expected_type
            or chunk.get("source_type") != expected_type
        ):
            errors.append(f"{evidence_id}: source_type mismatch")
        if (
            item.get("source_version") != expected_version
            or chunk.get("source_version") != expected_version
        ):
            errors.append(f"{evidence_id}: source_version mismatch")
        actual_sha = _sha256(root / source_path)
        if (
            item.get("source_sha256") != actual_sha
            or chunk.get("source_sha256") != actual_sha
        ):
            errors.append(f"{evidence_id}: source SHA-256 mismatch")
        anchor = item.get("anchor", "")
        if not anchor or _normalized(anchor) not in _normalized(chunk.get("text", "")):
            errors.append(f"{evidence_id}: anchor is absent from indexed chunk")
        if source_path == PAPER:
            page = item.get("page")
            if not isinstance(page, int) or page not in paper_pages:
                errors.append(f"{evidence_id}: invalid PDF page")
            elif chunk.get("location", {}).get("page") != page:
                errors.append(f"{evidence_id}: PDF page differs from indexed chunk")
            elif _normalized(anchor) not in _normalized(paper_pages[page]):
                errors.append(f"{evidence_id}: anchor is absent from parsed PDF page")
            if "lines" in item:
                errors.append(f"{evidence_id}: paper evidence cannot use code lines")
        else:
            lines = item.get("lines")
            if (
                not isinstance(lines, list)
                or len(lines) != 2
                or not all(isinstance(n, int) for n in lines)
                or lines[0] < 1
                or lines[1] < lines[0]
            ):
                errors.append(f"{evidence_id}: invalid code lines")
                continue
            location = chunk.get("location", {})
            if not (
                location.get("line_start", 10**9)
                <= lines[0]
                <= lines[1]
                <= location.get("line_end", -1)
            ):
                errors.append(f"{evidence_id}: code lines fall outside indexed chunk")
            raw_lines = (root / source_path).read_text(encoding="utf-8").splitlines()
            if _normalized(anchor) not in _normalized(
                "\n".join(raw_lines[lines[0] - 1 : lines[1]])
            ):
                errors.append(f"{evidence_id}: anchor is absent from raw code lines")
            if "page" in item:
                errors.append(f"{evidence_id}: code evidence cannot use a PDF page")

    if len(questions) != 8:
        errors.append(f"expected 8 Vim development questions, found {len(questions)}")
    seen_ids: set[str] = set()
    seen_groups: set[str] = set()
    for question in questions:
        question_id = question.get("id", "<missing id>")
        if question_id in seen_ids:
            errors.append(f"duplicate question id: {question_id}")
        seen_ids.add(question_id)
        group = question.get("leakage_group", "")
        if not group or group in seen_groups:
            errors.append(f"duplicate leakage_group: {group}")
        seen_groups.add(group)
        if question.get("split") != "dev" or not question_id.startswith("vim_dev_"):
            errors.append(f"{question_id}: invalid development identity")
        scope = question.get("scope", {})
        if (
            scope.get("paper_version") != PAPER_VERSION
            or scope.get("repo_commit") != REPO_COMMIT
            or scope.get("implementation") != "hustvl/Vim"
        ):
            errors.append(f"{question_id}: fixed Vim scope mismatch")
        if not question.get("question") or not question.get("gold_answer"):
            errors.append(f"{question_id}: question or gold answer is empty")
        claims = question.get("gold_claims", [])
        if not claims:
            errors.append(f"{question_id}: gold_claims is empty")
        required = question.get("required_evidence", [])
        cited: set[str] = set()
        claim_ids: set[str] = set()
        for claim in claims:
            if not claim.get("id") or claim["id"] in claim_ids or not claim.get("text"):
                errors.append(f"{question_id}: invalid or duplicate gold claim")
            claim_ids.add(claim.get("id", ""))
            if not claim.get("evidence_ids"):
                errors.append(f"{question_id}: claim without evidence IDs")
            cited.update(claim.get("evidence_ids", []))
        for evidence_id in (
            cited | set(required) | set(question.get("supporting_evidence", []))
        ):
            if evidence_id not in evidence_by_id:
                errors.append(f"{question_id}: unknown evidence {evidence_id}")
        if set(required) != cited:
            errors.append(
                f"{question_id}: required_evidence does not cover gold claims exactly"
            )
        if (
            question.get("question_provenance", {}).get("source_type")
            != "primary_source_derived"
        ):
            errors.append(
                f"{question_id}: provenance must describe primary-source derivation"
            )
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Vision Mamba development set: 8 questions and all evidence bindings passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
