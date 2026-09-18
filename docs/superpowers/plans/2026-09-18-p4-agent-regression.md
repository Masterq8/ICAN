# P4.4 Agent Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a new, durable 32-call Agent evaluation across four Swin development cases and four fixed QASPER external-regression cases without touching frozen test content.

**Architecture:** A focused P4 evaluation module derives query-only cases from the existing verified input loader, persists a source/input manifest before dispatch, and drives a separately budgeted `AgentService`. A script runs one fixed case at a time and a local audit validates journal, scope, identity and structured-claim requirements before a report is written.

**Tech Stack:** Python 3.12, Pydantic v2, asyncio, hashlib, filelock, existing AgentService/PaidJournal, pytest.

---

### Task 1: Query-only P4.4 case contract and manifest

**Files:**
- Create: `ican/evaluation/p4_agent.py`
- Create: `tests/test_p4_agent_evaluation.py`

- [x] **Step 1: Write failing case-selection tests**

```python
def test_cases_are_fixed_without_parsing_frozen_test(tmp_path, monkeypatch):
    cases, identity = build_p44_cases(tmp_path)
    assert [case.key for case in cases[:4]] == [
        "swin/dev/swin_dev_06", "swin/dev/swin_dev_05",
        "swin/dev/swin_dev_04", "swin/dev/swin_dev_12",
    ]
    assert len(cases) == 8 and identity["frozen_test_sha256"] == FROZEN_SHA256
```

- [x] **Step 2: Implement case selection and immutable manifest**

```python
def build_p44_cases(root: Path) -> tuple[list[P4AgentCase], dict]:
    inputs, _, fixed = load_inputs(root)
    # Pick known Swin dev IDs, then SHA-256-sort QASPER validation question IDs.
    # Never access the frozen test records.

def write_manifest(directory: Path, identity: dict) -> None:
    # Reject an existing unequal manifest; never overwrite a started run identity.
```

- [x] **Step 3: Run focused test and commit**

Run: `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_p4_agent_evaluation.py`

```powershell
git add ican/evaluation/p4_agent.py tests/test_p4_agent_evaluation.py
git commit -m "feat(evaluation): define fixed P4.4 Agent cases"
```

### Task 2: Bounded runner and local audit

**Files:**
- Modify: `ican/evaluation/p4_agent.py`
- Create: `scripts/evaluate_p4_agent.py`
- Modify: `tests/test_p4_agent_evaluation.py`

- [x] **Step 1: Write failing no-retry and audit tests**

```python
async def test_started_case_is_never_retried_and_shared_budget_is_32(tmp_path):
    runner = P4AgentEvaluationRunner(tmp_path, fake_service, max_calls=32)
    await runner.run_case(case)
    with pytest.raises(ValueError, match="already recorded"):
        await runner.run_case(case)

def test_audit_requires_shape_and_motivation_claim_states(tmp_path):
    report = audit_run(tmp_path, cases)
    assert report["status"] == "failed"
    assert "shape_claim_missing" in report["failures"]
```

- [x] **Step 2: Implement runner and audit**

```python
class P4AgentEvaluationRunner:
    async def run_case(self, case: P4AgentCase) -> AgentResponse:
        # Write .started JSON first, then call AgentService once and write response.
        # Existing response or marker raises; no retry path.

def audit_run(root: Path, directory: Path, cases: list[P4AgentCase]) -> dict:
    # Verify journal events, <=32 starts, response/request scope, source identity,
    # citation ownership and required Claim statuses for the two Swin cases.
```

- [x] **Step 3: Add CLI modes and run focused tests**

```powershell
D:/CondaEnv/ican/python.exe -m pytest -q tests/test_p4_agent_evaluation.py
```

- [x] **Step 4: Commit**

```powershell
git add ican/evaluation/p4_agent.py scripts/evaluate_p4_agent.py tests/test_p4_agent_evaluation.py
git commit -m "feat(evaluation): add bounded P4.4 Agent runner"
```

### Task 3: Real execution, audit and delivery

**Files:**
- Modify: `docs/p4-agent-report.md`
- Modify: `docs/p4-agent-guide.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/requirements-spec.md`

- [x] **Step 1: Run local full validation before spending budget**

```powershell
D:/CondaEnv/ican/python.exe -m pytest -q
D:/CondaEnv/ican/python.exe -m ruff check ican/evaluation scripts/evaluate_p4_agent.py tests/test_p4_agent_evaluation.py
D:/CondaEnv/ican/python.exe -m ruff format --check ican/evaluation scripts/evaluate_p4_agent.py tests/test_p4_agent_evaluation.py
```

- [x] **Step 2: Execute each of the eight frozen-manifest cases once**

```powershell
D:/CondaEnv/ican/python.exe scripts/evaluate_p4_agent.py run --case all --run-dir data/processed/evaluation/p4-v2
D:/CondaEnv/ican/python.exe scripts/evaluate_p4_agent.py audit --run-dir data/processed/evaluation/p4-v2
```

- [x] **Step 3: Record factual results and verify immutable inputs**

```powershell
D:/CondaEnv/ican/python.exe scripts/evaluate_p4_agent.py audit --run-dir data/processed/evaluation/p4-v2
git -c core.whitespace=cr-at-eol diff --check
```

Record exactly the saved model calls, statuses, Claim states, citations and returned usage. Hash-check the protected ledger, frozen Swin file and P2/P3 seals; do not print secrets.

- [x] **Step 4: Commit delivery documents**

```powershell
git add docs task_plan.md progress.md findings.md
git commit -m "docs(evaluation): record P4.4 Agent regression"
```
