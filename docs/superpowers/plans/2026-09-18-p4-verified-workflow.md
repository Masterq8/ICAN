# P4.5 Verified Workflow Implementation Plan

> **For agentic workers:** Use executing-plans inline in the current session. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make claim verification mandatory before a new-mode Agent answer, preserving the legacy tool loop and historical evaluations.

**Architecture:** Register a typed submit_claims tool on the existing PaperQAEnvironment. Service restricts tools by mode and budget stage; submission freezes evidence, verifies through ResearchService, then uses the existing one-shot Docs.aquery answer. Response status and workflow stages expose verification limits.

**Tech Stack:** Python, Pydantic, PaperQA2/Aviary, FastAPI, OpenAI SDK, pytest.

## Task 1: Submission and stage contracts

Files: `ican/agent/workflow.py`, `ican/agent/schema.py`, `tests/test_agent_verified_workflow.py`.

- [x] Write tests that reject unselected Claim IDs and missing required types.
- [x] Implement AnswerSubmission with strict evidence/claim bounds and validate_selection.

```python
submission = AnswerSubmission.model_validate(arguments)
submission.validate_selection(set(env.evidence_pool), request.required_claim_kinds)
```

- [x] Add versioned verified configuration and workflow fields; legacy default dataclass construction remains tool_loop.
- [x] Run `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_agent_verified_workflow.py`.

## Task 2: Mandatory native tool and driver routing

Files: `ican/agent/environment.py`, `ican/agent/service.py`, `ican/agent/runtime.py`, `ican/agent/prompts.py`, `configs/agent/v2.json`.

- [x] Add native fake-runtime tests: search then submit must create a Claim artifact before the answer; direct gen_answer and missing type submissions produce no paid answer.
- [x] Register submit_claims with typed submission schema; post-run oneOf branches expose kind-specific constraints.
- [x] In verified mode filter investigation tools and reserve the last planner call for submit_claims, including an empty evidence pool.

```python
if verified and finalization:
    available_tools = [tool for tool in tools if tool['function']['name'] == 'submit_claims']
```

- [x] Make a single tool's API tool_choice specify its function name; verify using a pure local options test.
- [x] Preserve all Claim evidence in the final context, propagate review/insufficiency status, and persist workflow stages.
- [x] Run Agent/API/Research tests and scoped Ruff; include implementation in delivery commit.

## Task 3: Narrow real acceptance and delivery

Files: `scripts/verify_agent_workflow.py`, `docs/p4-research-guide.md`, `task_plan.md`, `docs/development-roadmap.md`, `docs/requirements-spec.md`, `progress.md`, `findings.md`, `docs/problem-solution-log.md`.

- [x] Run full project tests before paid execution.
- [x] Create independent p4-v3 acceptance manifest/journal, code identities and started markers. Two Swin dev cases use explicit code_execution/inference type requirements and at most8 cumulative calls, no retry.

```powershell
D:/CondaEnv/ican/python.exe scripts/verify_agent_workflow.py
```

- [x] Inspect actual outputs; document failures without hiding or replaying old trajectories. Verify frozen test SHA and protected/P2/P3 inputs.
- [x] Correct roadmap completion language: records/rendering are foundations, automatic screening/extraction/report remain next work.
- [x] Commit delivered code/docs and report actual validation evidence; live acceptance remains failed.

## Acceptance result and remaining work

Two live cases failed after6 calls; no answer or claim artifact was generated. Post-run kind-specific schema and fresh final-draft messages passed offline checks only. P4.5 remains in_progress: validate provider protocol with fresh versioned budget, then proceed toP4.6. See docs/p4-verified-workflow-report.md. Engineering tasks checked above do not indicate successful live acceptance.
