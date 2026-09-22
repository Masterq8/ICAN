# P4.6 Quality Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and run an auditable eight-paper QASPER train acceptance set, add precise tool diagnostics and deterministic field-semantic checks, and publish manually reviewable quality metrics.

**Architecture:** Keep model output immutable. A pure submission parser produces structured protocol diagnostics, and a separate pure field-rule module adds semantic warnings without relabeling values. A bounded runner freezes evidence before any paid call, stores one result per fresh paper, then a deterministic scorer combines raw outputs with a checked-in manual review file.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, existing HybridEvidenceSearchService/ResearchAutoService/DeepSeekRuntime, JSON/Markdown artifacts.

---

### Task 1: Structured submission diagnostics

**Files:**
- Create: `ican/research/submission.py`
- Modify: `ican/research/auto_service.py`
- Test: `tests/test_research_submission.py`

- [ ] Write failing tests for no call, multiple calls, wrong tool, non-string arguments, invalid JSON, schema errors, out-of-scope evidence and success.
- [ ] Run `conda run -n ican python -m pytest tests/test_research_submission.py -q` and verify the new module is missing.
- [ ] Implement `diagnose_card_submission(action, allowed_ids)` returning a stable code, structured details and optional validated draft.
- [ ] Persist the diagnosis beside every raw model action before raising `ToolInputError`.
- [ ] Re-run the focused tests and `tests/test_research_auto.py`.

### Task 2: Deterministic field-semantic rules

**Files:**
- Create: `ican/research/field_rules.py`
- Modify: `ican/research/schema.py`
- Modify: `ican/research/service.py`
- Modify: `ican/research/auto_service.py`
- Test: `tests/test_research_field_rules.py`
- Test: `tests/test_research_service.py`

- [ ] Write table-driven failing tests for dataset/metric/result pass cases and strong cross-type conflicts.
- [ ] Implement `diagnose_field_assignment(name, value, quote)` with stable codes and suggested types; return no warning when lexical evidence is inconclusive.
- [ ] Add `semantic_diagnostics` to verified extraction fields and compute it server-side for automatic and manual submissions.
- [ ] Add the same definitions to the extraction prompt and emit comparison warnings for diagnosed fields.
- [ ] Run focused research tests.

### Task 3: Frozen eight-paper runner and scorer

**Files:**
- Create: `configs/evaluation/p46-quality-v1.json`
- Create: `ican/evaluation/research_card.py`
- Create: `scripts/evaluate_research_cards.py`
- Test: `tests/test_research_card_evaluation.py`

- [ ] Freeze eight unused QASPER train source IDs and one evidence-focused query per paper.
- [ ] Write failing tests for run-history exclusion, evidence identity hashing, one-call markers, diagnostic extraction and the four metric formulas.
- [ ] Implement `prepare`, `run` and `finalize` commands. `run` must reject existing markers and cap the journal at eight calls.
- [ ] Verify `prepare` produces eight distinct papers, six evidence items per paper and a reproducible manifest hash without a paid call.

### Task 4: Real run, manual audit and report

**Files:**
- Create: `docs/evaluation/p46-quality-v1/manifest.json`
- Create: `docs/evaluation/p46-quality-v1/manual-review.json`
- Create: `docs/evaluation/p46-quality-v1/report.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/problem-solution-log.md`

- [ ] Run each frozen paper once with `deepseek-flash`; never rerun a started case.
- [ ] Review the exact six evidence items and raw submission for every case; record support, assigned/correct type, expected-present fields and omissions.
- [ ] Run `finalize` to calculate the four required metrics plus present-field recall and confusion counts.
- [ ] Check report arithmetic against raw counts and document every non-success code with concrete details.
- [ ] Run Ruff, the full Python suite, frontend production build, protected-file hash checks and secret scan.

### Task 5: Review checkpoint

**Files:**
- Review all files changed since `0cdb7eb`.

- [ ] Inspect `git diff --check`, ignored runtime artifacts and tracked evaluation artifacts.
- [ ] Request independent code review before committing the completed node.
- [ ] Fix important findings, rerun affected checks, then commit and push the checkpoint branch.
