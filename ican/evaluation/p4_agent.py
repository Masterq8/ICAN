"""Fixed-case inputs and immutable manifests for P4.4 Agent evaluation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ican.agent.schema import AgentRequest, AgentResponse

from .data import Case, digest, load_inputs

SWIN_CASE_IDS = (
    "swin_dev_06",
    "swin_dev_05",
    "swin_dev_04",
    "swin_dev_12",
)
FROZEN_SHA256 = "5b2db3539abd08fd52b1e2d6aab4b5b78a1398d3738e3ebce9764c35b55c74b2"


@dataclass(frozen=True)
class P4AgentCase:
    """A fixed, query-only P4.4 request and its audit requirements."""

    key: str
    request: AgentRequest
    required_claim_status: str | None = None

    def record(self) -> dict:
        return {
            "key": self.key,
            "request": self.request.model_dump(mode="json"),
            "required_claim_status": self.required_claim_status,
        }


def _external_order(case: Case) -> str:
    return hashlib.sha256(case.id.encode("utf-8")).hexdigest()


def build_p44_cases(root: Path) -> tuple[list[P4AgentCase], dict]:
    """Return fixed development and external cases without accessing frozen records."""

    inputs, _, fixed = load_inputs(Path(root))
    by_key = {case.key: case for case in inputs}
    selected: list[P4AgentCase] = []
    requirements = {
        "swin_dev_04": "blocked_by_precondition",
        "swin_dev_12": "requires_review",
    }
    for case_id in SWIN_CASE_IDS:
        case = by_key.get(f"swin/dev/{case_id}")
        if case is None:
            raise ValueError(f"Required P4.4 development case is absent: {case_id}")
        selected.append(
            P4AgentCase(
                key=case.key,
                request=AgentRequest(
                    **case.request(), strategy="hybrid_rerank", family="swin_v1"
                ),
                required_claim_status=requirements.get(case_id),
            )
        )
    external = sorted(
        (
            case
            for case in inputs
            if case.dataset == "qasper" and case.split == "validation"
        ),
        key=_external_order,
    )[:4]
    if len(external) != 4:
        raise ValueError("Expected at least four fixed QASPER validation cases")
    selected.extend(
        P4AgentCase(
            key=case.key,
            request=AgentRequest(**case.request(), strategy="dense"),
        )
        for case in external
    )
    frozen = digest(Path(root) / "data/eval/swin_test.jsonl")
    if frozen != FROZEN_SHA256:
        raise ValueError("Frozen test bytes changed")
    identity = {
        "version": "p4-agent-evaluation-v2",
        "fixed_input_sha256": fixed,
        "frozen_test_sha256": frozen,
        "cases": [case.record() for case in selected],
    }
    return selected, identity


def write_manifest(directory: Path, identity: dict) -> Path:
    """Persist one canonical identity and reject any future replacement."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "manifest.json"
    content = json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing != content:
            raise ValueError("P4.4 evaluation manifest identity changed")
        return target
    target.write_text(content, encoding="utf-8", newline="\n")
    return target


def _case_token(case: P4AgentCase) -> str:
    return hashlib.sha256(case.key.encode("utf-8")).hexdigest()[:16]


def _case_paths(directory: Path, case: P4AgentCase) -> tuple[Path, Path]:
    token = _case_token(case)
    return (
        Path(directory) / f"{token}.started.json",
        Path(directory) / f"{token}.response.json",
    )


class P4AgentEvaluationRunner:
    """Persist each case before dispatching it once through an Agent service."""

    def __init__(
        self, directory: Path, cases: list[P4AgentCase], identity: dict, service
    ):
        self.directory = Path(directory)
        self.cases = {case.key: case for case in cases}
        self.identity = identity
        self.service = service
        write_manifest(self.directory, self.identity)

    def _paths(self, case: P4AgentCase) -> tuple[Path, Path]:
        return _case_paths(self.directory, case)

    async def run_case(self, case: P4AgentCase) -> AgentResponse:
        expected = self.cases.get(case.key)
        if expected is None or expected.record() != case.record():
            raise ValueError("P4.4 case is not present in the fixed manifest")
        marker, output = self._paths(case)
        if output.exists():
            raise ValueError("P4.4 case already recorded; automatic retry is disabled")
        if marker.exists():
            raise ValueError("P4.4 case already started; inspect retained result")
        marker.write_text(
            json.dumps({"case": case.record()}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        response = await self.service.run(case.request)
        output.write_text(
            json.dumps(
                {"case": case.record(), "response": response.model_dump(mode="json")},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return response


def _claim_statuses(response: AgentResponse) -> set[str]:
    statuses = set()
    for artifact in response.artifacts:
        if artifact.get("kind") != "claim_verification":
            continue
        for verdict in artifact.get("verdicts", []):
            status = verdict.get("status")
            if isinstance(status, str):
                statuses.add(status)
    return statuses


def _citation_scope_failures(case: P4AgentCase, response: AgentResponse) -> list[str]:
    failures = []
    prefixes = case.request.filters.path_prefixes
    types = case.request.filters.source_types
    if response.answer is None:
        return failures
    for citation in response.answer.citations:
        source = citation.evidence.source
        path = source.source_path.replace("\\", "/")
        if prefixes and not any(path.startswith(prefix) for prefix in prefixes):
            failures.append("citation_scope_path")
        if types and source.source_type not in types:
            failures.append("citation_scope_type")
    return failures


def _journal_failures(directory: Path, max_calls: int) -> tuple[list[str], int]:
    path = Path(directory) / "paid-journal.jsonl"
    if not path.exists():
        return ["journal_missing"], 0
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except json.JSONDecodeError:
        return ["journal_invalid_json"], 0
    started = [row for row in rows if row.get("event") == "started"]
    failures = []
    if len(started) > max_calls:
        failures.append("journal_budget_exceeded")
    start_ids = {row.get("call_id") for row in started}
    terminal = [row for row in rows if row.get("event") in {"completed", "error"}]
    terminal_ids = [row.get("call_id") for row in terminal]
    if len(terminal_ids) != len(set(terminal_ids)):
        failures.append("journal_duplicate_terminal")
    if set(terminal_ids) != start_ids:
        failures.append("journal_unpaired_events")
    return failures, len(started)


def audit_run(
    directory: Path,
    cases: list[P4AgentCase],
    identity: dict,
    *,
    max_calls: int = 32,
) -> dict[str, Any]:
    """Check run identity, no-retry records, evidence scope and required claims."""

    directory = Path(directory)
    failures: list[str] = []
    manifest = directory / "manifest.json"
    if not manifest.exists():
        failures.append("manifest_missing")
    else:
        try:
            if json.loads(manifest.read_text(encoding="utf-8")) != identity:
                failures.append("manifest_identity_changed")
        except json.JSONDecodeError:
            failures.append("manifest_invalid_json")
    results = []
    for case in cases:
        marker, output = _case_paths(directory, case)
        if not marker.exists():
            failures.append(f"{case.key}:start_missing")
        if not output.exists():
            failures.append(f"{case.key}:response_missing")
            continue
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
            if payload.get("case") != case.record():
                failures.append(f"{case.key}:request_identity_changed")
                continue
            response = AgentResponse.model_validate(payload.get("response"))
        except (json.JSONDecodeError, ValueError):
            failures.append(f"{case.key}:response_invalid")
            continue
        if response.usage.paid_calls > 4:
            failures.append(f"{case.key}:case_budget_exceeded")
        if (
            case.required_claim_status
            and case.required_claim_status not in _claim_statuses(response)
        ):
            failures.append(f"{case.key}:claim_status_missing")
        failures.extend(
            f"{case.key}:{reason}"
            for reason in _citation_scope_failures(case, response)
        )
        results.append(
            {
                "key": case.key,
                "status": response.status,
                "stop_reason": response.stop_reason,
                "usage": response.usage.model_dump(mode="json"),
                "claim_statuses": sorted(_claim_statuses(response)),
            }
        )
    journal_failures, started = _journal_failures(directory, max_calls)
    failures.extend(journal_failures)
    return {
        "status": "passed" if not failures else "failed",
        "failures": sorted(set(failures)),
        "journal_started_calls": started,
        "max_calls": max_calls,
        "cases": results,
    }
