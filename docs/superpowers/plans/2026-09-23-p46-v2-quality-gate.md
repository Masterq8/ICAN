# P4.6 v2 Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a sealed `deepseek-v4-pro` acceptance on eight never-used QASPER train papers, decide P4.6 against frozen quality gates, and add a paper-scoped review fallback only if the gate fails.

**Architecture:** A v2 evaluator selects and freezes eight source IDs, makes exactly one model call per paper, preserves every raw action and usage record, and scores all parseable occurrences plus all expected field-presence slots. Existing submission and deterministic field rules remain the source of protocol and classification diagnostics. If the frozen gate fails, the research API projects raw entries into high-confidence fields and review candidates; the Vue workspace lets the user inspect evidence, search within the same paper, correct the entry, and save a normal research-record revision.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, pytest, JSON/JSONL sealed artifacts, Vue 3, TypeScript, Vite, Vitest, DeepSeek OpenAI-compatible API.

---

## Frozen acceptance contract

- Papers, in order: `qasper:1601.02166`, `qasper:1601.06081`, `qasper:1601.06738`, `qasper:1602.00812`, `qasper:1602.03661`, `qasper:1604.00117`, `qasper:1604.00125`, `qasper:1604.05781`.
- Corpus: `data/processed/qasper_external/v1/train_corpus.jsonl`, QASPER `train` split only.
- Corpus preparation: expand the pinned local QASPER train sample from the first 20 to the first 23 lexicographic paper IDs, then rebuild its chunks and index; the validation sample remains fixed at 10.
- Freshness roots: `data/processed/evaluation` and `data/processed/research`; preparation must fail if any frozen ID is found there.
- Generation model: `deepseek-v4-pro`; exactly one generation request per paper, with no retry, substitution, or prompt rerun.
- Tool success gate: at least `7/8` accepted submissions.
- Raw evidence support gate: at least `90%` of every parseable raw field occurrence.
- Raw field-type gate: at least `85%` of every parseable raw field occurrence.
- Missing-field identification gate: at least `85%` across all nine expected field types for all papers.
- Hard failures: any evidence outside the frozen paper, missing call trace, source-integrity failure, or unexplained server failure.
- AI adjudication remains labelled `ai`; human review remains `pending` until a person edits and finalizes the bound worksheet.

### Task 1: Add the v2 evaluator contract and tests

**Files:**
- Create: `configs/evaluation/p46-quality-v2.json`
- Create: `scripts/evaluate_research_cards_v2.py`
- Create: `tests/test_research_card_v2_evaluation.py`
- Modify: `configs/chunking/v1.json`
- Modify: `configs/indexing/v1.json`
- Regenerate: `data/processed/qasper_external/v1/`
- Regenerate: `data/processed/qasper_external/chunks/v1/`
- Regenerate: `data/eval/qasper_external/v1/train_questions.jsonl`
- Regenerate: `data/catalog/qasper-external.json`
- Reuse: `ican/evaluation/research_card.py`
- Reuse: `ican/evaluation/research_audit.py`

- [x] Run `conda run -n ican python scripts/prepare_qasper.py --train-count 23 --validation-count 10` against the already downloaded pinned parquet and dataset card.
- [x] Update the QASPER parent-manifest hash in `configs/chunking/v1.json`, rebuild chunks, then update the QASPER chunk-manifest and evaluation hashes in `configs/indexing/v1.json` and rebuild the index.
- [x] Verify the first 20 train papers are byte-for-byte unchanged as records, the validation artifacts are unchanged, and the three added train papers are exactly `1604.00117`, `1604.00125`, and `1604.05781`.
- [x] Write a failing test that loads the v2 config and asserts the eight source IDs, order, split, model, hard call cap, and four thresholds above.
- [x] Write a failing test that normalizes IDs to `qasper:<paper_id>` and rejects duplicate IDs, fewer or more than eight IDs, a used source ID, a model other than `deepseek-v4-pro`, and any retry allowance above zero.
- [x] Implement the frozen JSON config and a `prepare` command that reads the corpus, groups chunks by `source_id`, checks both freshness roots, and writes `data/processed/evaluation/p46-quality-v2/runtime/frozen-cases.json`.
- [x] Make preparation freeze each paper title, selected evidence-unit IDs, evidence text, corpus file SHA-256, config SHA-256, and current Git source commit.
- [x] Make preparation refuse a dirty tree except for ignored runtime output, and refuse to overwrite a started or sealed run.
- [x] Run `python -m pytest tests/test_research_card_v2_evaluation.py -q` and require all tests to pass.
- [x] Commit the config, runner, and tests with message `Add sealed P4.6 v2 quality gate`.

### Task 2: Enforce one paid generation call per paper

**Files:**
- Modify: `scripts/evaluate_research_cards_v2.py`
- Modify: `tests/test_research_card_v2_evaluation.py`
- Runtime: `data/processed/evaluation/p46-quality-v2/runtime/call-journal.jsonl`
- Runtime: `data/processed/evaluation/p46-quality-v2/runtime/raw-actions/`
- Runtime: `data/processed/evaluation/p46-quality-v2/runtime/case-results/`

- [x] Write a failing test with a fake model client proving `run` invokes each source exactly once, records failures without retry, and stops once eight terminal records exist.
- [x] Write a failing resume test proving a source with a `started` journal event but no terminal event is marked `interrupted_unknown` and is never called again automatically.
- [x] Implement append-only `started`, `completed`, and `failed` journal events with source ID, request hash, model, timestamp, status, usage, response ID, and sanitized server diagnostics.
- [x] Save the exact raw tool action before submission parsing, then run the current multi-entry `diagnose_card_submission(..., legacy=False)` path and save accepted or rejected case output.
- [x] Classify errors as transport, HTTP status, provider payload, missing tool call, JSON/schema, evidence-scope, or local persistence; never collapse all failures to `ToolInputError`.
- [x] Add `--dry-run` and fake-client seams that exercise the full persistence path without network access.
- [x] Run `python -m pytest tests/test_research_card_v2_evaluation.py tests/test_research_submission.py -q`.
- [x] Commit with message `Enforce P4.6 v2 call budget and diagnostics`.

### Task 3: Prepare, inspect, and freeze before spending the budget

**Files:**
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/frozen-cases.json`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/preflight.json`
- Update: `docs/problem-solution-log.md`

- [x] Run `python scripts/evaluate_research_cards_v2.py prepare --config configs/evaluation/p46-quality-v2.json`.
- [x] Inspect the eight titles and frozen evidence for empty text, duplicate evidence IDs, truncated quotes, and prior-ID overlap; abort preparation if any check fails.
- [x] Run the evaluator preflight against the configured endpoint without generating a card: validate environment-variable presence, model name, API compatibility, and writable runtime paths while keeping secrets out of artifacts and terminal output.
- [x] Record preparation findings and any resolved issue in `docs/problem-solution-log.md` without recording the API key.
- [x] Commit the frozen manifest and preflight record with message `Freeze fresh QASPER v2 acceptance cases`.
- [x] Record source commit `5a4bd98fc0518e85d61c2f7e3e689527f92bcad5` as the sole allowed code identity in `preflight.json`; no code or config edit is allowed during Task 4.

### Task 4: Execute and seal the eight real calls

**Files:**
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/call-journal.jsonl`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/raw-actions/*.json`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/case-results/*.json`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/seal.json`

- [x] Run `python scripts/evaluate_research_cards_v2.py run --config configs/evaluation/p46-quality-v2.json` once with `deepseek-v4-pro`.
- [x] Do not retry any failed, interrupted, or malformed case; preserve the provider response and diagnostic category as-is.
- [x] Run `python scripts/evaluate_research_cards_v2.py seal --config configs/evaluation/p46-quality-v2.json` immediately after all eight sources have terminal or interrupted records.
- [x] Verify the seal contains hashes for the config, frozen cases, journal, every raw action, every case result, source commit, model name, and aggregate token/cost metadata.
- [x] Run `python scripts/evaluate_research_cards_v2.py audit --config configs/evaluation/p46-quality-v2.json`; require source commit, call count, model, freshness, and artifact hashes to pass before scoring.

### Task 5: Adjudicate every occurrence and compute the frozen decision

**Files:**
- Modify: `scripts/evaluate_research_cards_v2.py`
- Modify: `tests/test_research_card_v2_evaluation.py`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/ai-review.json`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/manual-review.json`
- Generate: `data/processed/evaluation/p46-quality-v2/runtime/metrics.json`
- Create: `docs/evaluation/p46-quality-v2/report.md`
- Create: `docs/evaluation/p46-quality-v2/human-review.md`

- [x] Write failing scorer tests proving repeated same-type entries are separate occurrences, rejected but parseable raw fields remain in the denominators, and all `8 × 9` expected type-presence decisions are counted.
- [x] Write failing tests proving deterministic dataset/metric/result rules emit warnings and reviewer context but never silently relabel or delete model output.
- [x] Implement the AI review sheet with immutable occurrence IDs, raw field/value/evidence, paper-scoped evidence context, deterministic warnings, reviewer identity `ai`, decision, and reason.
- [x] For each occurrence, decide evidence support and field-type correctness; for every paper/type pair, decide present, correctly missing, or missed. Preserve ambiguous cases as failures with an explicit reason instead of excluding them.
- [x] Bind `manual-review.json` to hashes of the seal, metrics input, and AI review. Initialize human status to `pending` and do not present AI adjudication as human review.
- [x] Implement `finalize` to recompute tool success, evidence support, type correctness, and missing-field identification from the bound review sheet; reject modified inputs or unrecognized occurrence IDs.
- [x] Generate `report.md` with all four numerators/denominators, per-paper results, protocol/server/model diagnostics, gate decision, hard-failure findings, model usage, and artifact hashes.
- [x] Generate `human-review.md` with exact commands for editing and finalizing a later human audit.
- [x] Run `python -m pytest tests/test_research_card_v2_evaluation.py tests/test_research_card_evaluation.py -q`.
- [ ] If every frozen gate passes, update `task_plan.md` and `progress.md` to mark P4.6 complete, then skip Task 6.
- [x] If any frozen gate fails, record the failed gate and continue to Task 6 without rerunning any paper.
- [x] Commit the sealed results and decision with message `Record P4.6 v2 quality acceptance`.

### Task 6: Add the high-confidence and user-review fallback only on gate failure

**Files:**
- Create: `ican/research/confidence.py`
- Modify: `ican/research/auto_schema.py`
- Modify: `ican/research/auto_service.py`
- Modify: `ican/api/app.py`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/style.css`
- Create: `tests/test_research_confidence.py`
- Modify: `tests/test_research_auto.py`
- Modify: `tests/test_research_auto.py` (API and service integration)

- [x] Write projector tests for same-paper evidence, exact quote, and deterministic-rule conflicts.
- [x] Write regression tests proving cross-paper evidence cannot become high-confidence and that unsupported or semantically conflicted fields are excluded from comparison; preserve the existing multi-entry comparison block.
- [x] Add high-confidence and review-candidate response models with occurrence, source, proposed value/evidence, reason codes, and allowed user actions. The existing `status` union carries generation outcome.
- [x] Return `completed` for a saved screening card and `review_required` otherwise; persist only independently high-confidence fields from rejected actions.
- [x] Add paper-scoped evidence search forced to selected source identity, path, and version; filter returned retrieval results again server-side.
- [x] Verify status, confidence projection, scoped search, persistence/reload, and same-paper evidence validation in service/API tests.
- [x] Update Vue workspace with high-confidence and review sections, same-paper search, field editors, revision save, ignore, and manual entry when no tool action exists.
- [x] Comparison only accepts supported fields without semantic diagnostics; ambiguous multiple same-name entries block ranking.
- [x] Frontend test runner is not configured; rely on Python API integration coverage and Vue typecheck/production build without adding a test framework.
- [x] Run `conda run -n ican python -m pytest tests/test_research_confidence.py tests/test_research_auto.py tests/test_research_api.py -q` (18 passed).
- [x] Run `npm run build` from `frontend` (vue-tsc and Vite production build passed).
- [x] Update research guide, task plan, progress, and problem log with fallback behavior and failed acceptance evidence.
- [x] Commit with message `Add paper-scoped research review fallback`.

### Task 7: Final regression, review, and push

**Files:**
- Review all files changed by Tasks 1–6.

- [ ] Run the full Python suite: `conda run -n ican python -m pytest -q`.
- [x] Frontend test runner is not configured; run the frontend typecheck and production build with `npm run build` (passed).
- [x] Re-run the sealed audit and verify that post-run code changes did not alter the recorded v2 source commit or any sealed hash.
- [x] Check `git diff --check`, `git status --short`, staged secret scanning, and confirm no `.env`, API key, or raw credential appears in tracked content.
- [x] Review the final diff against the design spec and record the browser interaction limitation and semantic-confidence boundary in `docs/problem-solution-log.md` and `docs/p4-research-guide.md`.
- [ ] Commit final documentation/test-only changes, push `codex/p4-agent-tools`, and report the commit IDs, exact test results, four metrics, gate decision, model-call count, and whether Task 6 was activated.
