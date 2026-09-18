# P4.1–P4.2 Agent Tools Implementation Plan

> Execute inline using executing-plans; P4 is explicitly authorized. Request independent code review at the main implementation checkpoint. No new design permission required.

**Goal:** Deliver a runnable, bounded PaperQA2 domain Agent with actual DeepSeek tool selection and deterministic configuration/calculation tools.

**Architecture:** Verified corpus and user scope → PaperQAEnvironment extension → native OpenAI tool requests → scoped local tools → existing PaperQA2 evidence answer → auditable stop state. Tool artifacts stay distinct from original evidence.

**Tech Stack:** pinned paper-qa/Aviary, OpenAI SDK, Python AST/Decimal/PyYAML, Qdrant/P3, FastAPI, filelock.

## 1. Contracts, corpus and deterministic tools

- [x] Create `ican/agent/schema.py`, `corpus.py`, `calculation.py`, `configuration.py`, `configs/agent/v1.json`.
- [x] Verify existing chunk/source bytes and request scope before direct reads; no gold files or arbitrary filesystem access.
- [x] Test Decimal AST bounds, exact default assignments, BASE ordering/cycles, opts/CLI precedence and provenance before integrating models.

## 2. PaperQA2 environment and bounded runtime

- [x] Create `ican/agent/environment.py`, `runtime.py`, `service.py`, `journal.py`, `prompts.py`.
- [x] Override upstream tools; run actual PaperQAEnvironment step/dispatch and EnvironmentState history. Preserve existing raw evidence adapter, add distinct tool-result section only for P4.
- [x] Validate named tools and arguments before dispatch, serial execution, bounded evidence context, exact source scope, one index fingerprint, repeat-action cache, and explicit stop reasons.
- [x] Pro planner / Flash answer via SDK retries0; reserve every actual paid request in persistent journal, including errors and started-only calls.
- [x] Run fake-model workflows through real upstream tools and PaperQA2 answer bridge; test budget/timeout/failure and no fake completion.

## 3. API and actual acceptance

- [x] Extend lazy `create_app` with injectable Agent service and `/v1/agent/run`; health remains model-free.
- [x] Add `scripts/verify_p4_agent.py` with cumulative max40 journal, source/config identities, retained trajectory and protected frozen hash only.
- [x] Run selected Swin development tasks and inspect actual answers/citations; retain failed semantic acceptance, source versions and new judgments.
- [ ] External Agent attribution/insufficiency and full developer regression: deferred to P4.4; 39/40 paid requests used, no external benchmark claimed.
- [x] Check response-model identities and real tokens; document cost estimates separately from unknown actual bill.

## 4. Review and local delivery

- [x] Independent core review completed; important discoveries resolved. Final integer arithmetic/finalization changes self-reviewed and tested; follow-up reviewer unavailable after usage-limit error, no third independent conclusion claimed.
- [x] Run meaningful full tests and scoped Ruff/format, protected input and old generation hashes, staged credentials scan.
- [x] Update task_plan/progress/findings/requirements/roadmap/problem log; document P4.1/P4.2 actual delivery and P4.3/P4.4 pending. Local commit on `codex/p4-agent-tools`, no push.
