# P4.6 Quality Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Freeze and run an auditable eight-paper QASPER train acceptance set, add precise tool diagnostics and deterministic field-semantic checks, and publish manually reviewable quality metrics.

**Architecture:** Keep model output immutable. A pure submission parser produces structured protocol diagnostics, and a separate pure field-rule module adds semantic warnings without relabeling values. A bounded runner freezes evidence before any paid call, stores one result per fresh paper, then a deterministic scorer combines raw outputs with a checked-in manual review file.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, existing HybridEvidenceSearchService/ResearchAutoService/DeepSeekRuntime, JSON/Markdown artifacts.

---

### Task 1: Structured submission diagnostics

**Files:**
- Create: `ican/research/submission.py`
- Modify: `ican/research/auto_service.py`
- Test: `tests/test_research_submission.py`

- [x] Write failing tests for no call, multiple calls, wrong tool, non-string arguments, invalid JSON, schema errors, out-of-scope evidence and success.
- [x] Run `conda run -n ican python -m pytest tests/test_research_submission.py -q` and verify the new module is missing.
- [x] Implement `diagnose_card_submission(action, allowed_ids)` returning a stable code, structured details and optional validated draft.
- [x] Persist the diagnosis beside every raw model action before raising `ToolInputError`.
- [x] Re-run the focused tests and `tests/test_research_auto.py`.

### Task 2: Deterministic field-semantic rules

**Files:**
- Create: `ican/research/field_rules.py`
- Modify: `ican/research/schema.py`
- Modify: `ican/research/service.py`
- Modify: `ican/research/auto_service.py`
- Test: `tests/test_research_field_rules.py`
- Test: `tests/test_research_service.py`

- [x] Write table-driven failing tests for dataset/metric/result pass cases and strong cross-type conflicts.
- [x] Implement `diagnose_field_assignment(name, value, quote)` with stable codes and suggested types; return no warning when lexical evidence is inconclusive.
- [x] Add `semantic_diagnostics` to verified extraction fields and compute it server-side for automatic and manual submissions.
- [x] Add the same definitions to the extraction prompt and emit comparison warnings for diagnosed fields.
- [x] Run focused research tests.

### Task 3: Frozen eight-paper runner and scorer

**Files:**
- Create: `configs/evaluation/p46-quality-v1.json`
- Create: `ican/evaluation/research_card.py`
- Create: `scripts/evaluate_research_cards.py`
- Test: `tests/test_research_card_evaluation.py`

- [x] Freeze eight unused QASPER train source IDs and one evidence-focused query per paper.
- [x] Write failing tests for run-history exclusion, evidence identity hashing, one-call markers, diagnostic extraction and the four metric formulas.
- [x] Implement `prepare`, `run` and `finalize` commands. `run` must reject existing markers and cap the journal at eight calls.
- [x] Verify `prepare` produces eight distinct papers, six evidence items per paper and a reproducible manifest hash without a paid call.

### Task 4: Real run, manual audit and report

**Files:**
- Create: `docs/evaluation/p46-quality-v1/manifest.json`
- Create: `docs/evaluation/p46-quality-v1/manual-review.json`
- Create: `docs/evaluation/p46-quality-v1/report.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/problem-solution-log.md`

- [x] Run each frozen paper once with `deepseek-flash`; never rerun a started case.
- [x] Assistant initial audit of the exact six evidence items and raw submission for every case; record support, assigned/correct type, expected-present fields and omissions.
- [ ] Human confirmation of field types, source support and omissions using `human-review.md`; labels remain `human_review_status=pending`.
- [x] Run `finalize` to calculate the four required metrics plus present-field recall and confusion counts.
- [x] Check report arithmetic against raw counts and document every non-success code with concrete details.
- [x] Run Ruff, the full Python suite, frontend production build, protected-file hash checks and secret scan.

### Task 5: Review checkpoint

**Files:**
- Review all files changed since `0cdb7eb`.

- [x] Inspect `git diff --check`, ignored runtime artifacts and tracked evaluation artifacts.
- [x] Request independent code review before committing the completed node.
- [x] Fix important findings and rerun affected checks: 303 passed / 1 skipped, Ruff and frontend build passed, 61 protected hashes unchanged.
- [x] Prepare reviewed checkpoint for commit/push; verify remote synchronization from Git, independently of this checklist.

## 2026-09-23 checkpoint

Eight calls completed once at source commit `2937a56`; 2 accepted, 6 rejected for duplicate field names. Preserve the original accepted-only metrics and explicitly label all-raw-field metrics as a posthoc supplement. Assistant labels are provisional. Source, artifact, journal and occurrence hashes bind the offline scorer to this run. No paid reruns. Independent review found no remaining Critical/Important issues after fixes. Next product change: design multi-entry fields and test with offline replay, retaining the original failures.

- [x] 2026-09-23 user-authorized Pro-assisted second AI audit: 16 reviewer calls, 59 occurrences and 72 presence slots checked, identities retained, finalize recalculated. This does not check off human confirmation. See `docs/evaluation/p46-quality-v1/review-adjudication.md`.
