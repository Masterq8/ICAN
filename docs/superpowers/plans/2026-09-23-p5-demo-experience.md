# P5 Demo Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Complete P5 demo experience with paper-history browsing and deterministic diffs, truthful task status, a no-network read-only Swin demo, and recoverable online errors.

**Architecture:** Extend the existing FastAPI research-record service with a defensive history read endpoint. Keep deterministic version pairing in a small frontend utility. Package one source-linked Swin fixture as a local frontend asset and switch the existing Vue workbench into a visibly read-only demo state without calling APIs or writing records. Add bounded execution-stage data to auto-card responses based on actual synchronous control flow.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, Vue 3, TypeScript, Vite, Vitest, browser verification.

---

## Execution note

Implemented in the existing working tree. No commit was created because P4.6 and Vision Mamba work already had uncommitted changes in shared files; bundling those changes would make review and rollback unsafe.

## File map

- Modify `ican/research/store.py`: list valid records for one subject, isolate corrupt files, and return safe diagnostics.
- Modify `ican/research/service.py`: expose sorted history grouped by screening/extraction.
- Modify `ican/api/app.py`: add `GET /v1/research/history/{source_id}`.
- Modify `tests/test_research_service.py`, `tests/test_research_api.py`: cover ordering, corruption, subject isolation, response shape.
- Modify `ican/research/auto_schema.py`, `ican/research/auto_service.py`: typed, bounded actual-stage summary for auto-card.
- Modify `tests/test_research_auto.py`: test success, tool rejection, model failure and budget exhaustion summaries.
- Create `frontend/src/versionDiff.ts`: pair duplicate fields deterministically and classify field/decision/claim changes.
- Create `frontend/src/versionDiff.test.ts`; modify `frontend/package.json` and `frontend/package-lock.json`: Vitest test command and diff coverage.
- Create `frontend/src/demo/swin-case.json`: fixed, source-linked, read-only fixture including evidence, candidate, screening/extraction revisions and a one-paper report snapshot.
- Modify `frontend/src/types.ts`, `frontend/src/api.ts`: history and stage types and history request.
- Modify `frontend/src/App.vue`, `frontend/src/style.css`: history panel, diff table, demo entry/exit, offline-safe startup, status/error states and read-only controls.
- Modify `README.md` and `docs/p5-web-guide.md`: describe live and demo modes and limitations.

## Task 1: Defensive history data and endpoint

**Files:** `ican/research/store.py`, `ican/research/service.py`, `ican/api/app.py`, `tests/test_research_service.py`, `tests/test_research_api.py`

- [x] Add a `ResearchStore.list_for_subject(subject_source_id)` method that scans only `*.json`, validates each record independently, filters exact subject IDs, and sorts descending by `(created_at, str(record_id))`. Return `(records, diagnostics)` where each diagnostic contains only the bad filename stem and a fixed error code (`invalid_json`, `invalid_record`, or `unreadable`), never file contents.
- [x] Add tests for both record types, unrelated-subject exclusion, deterministic equal-time ordering, and one malformed JSON beside valid records. Run `pytest tests/test_research_service.py -q`; expect the new tests to fail because the method is absent.
- [x] Add a service method `history(subject_source_id)` returning `{"screening": [...], "extraction": [...], "diagnostics": [...]}`. Preserve `ResearchRecord` models and already-recorded evidence metadata.
- [x] Add `GET /v1/research/history/{source_id}` with a 256-character path parameter bound and return the service payload. Add API tests using an injected fake store/service and assert 200, grouping, stable order and safe diagnostics.
- [x] Run `pytest tests/test_research_service.py tests/test_research_api.py -q`; expect all pass. Commit as `feat: expose defensive research record history`.

## Task 2: Deterministic arbitrary-version comparison

**Files:** `frontend/src/versionDiff.ts`, `frontend/src/versionDiff.test.ts`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/types.ts`

- [x] Add Vitest (`npm install -D vitest`) and a `"test": "vitest run"` script. Create tests first for unchanged, added, removed and modified fields, duplicate same-name fields, different-name pairing, screening decision changes, and mismatched record type/subject rejection. Run `npm test -- --reporter=dot`; expect the module import to fail.
- [x] Implement `compareRecords(left, right)` over `ResearchRecord`. Throw when subject or `record_type` differ. For extraction, group in source order by field name; pair normalized exact `(name,value)` matches first, then pair remaining same-name entries in appearance order. Mark pairs ambiguous when duplicate same-name candidates existed on either side. Produce rows with `added|removed|modified|unchanged`, both original field/claim/evidence payloads, and `needsReview`.
- [x] For screening, return decision and claim rows with status, quote/statement and evidence locations unchanged from input. Do not synthesize a model-generated summary or actor label.
- [x] Run `npm test -- --reporter=dot` and `npm run build`; expect tests and production build to pass. Commit as `feat: compare research record revisions deterministically`.

## Task 3: Truthful auto-card stage summaries

**Files:** `ican/research/auto_schema.py`, `ican/research/auto_service.py`, `tests/test_research_auto.py`, `frontend/src/types.ts`

- [x] Add enum-backed `AutoStage` (`evidence_preparation`, `model_submission`, `result_validation`, `record_save`) and `AutoStageResult(status: completed|failed|skipped)` to `AutoCardResponse`, plus a bounded `stop_reason` string. Add schema tests to ensure unknown stage/status values are rejected.
- [x] Construct stages in `ResearchAutoService.auto_card` at the real control-flow boundaries: evidence prepared after `_paper_evidence` and corpus creation; model submission completed only after runtime returns; validation completed only after `diagnose_card_submission`; record save completed only after persistence returns. Failed stages match the thrown/diagnosed outcome; later stages are `skipped`. Use fixed stop codes, not raw exception text or stack traces. Budget exhaustion retains HTTP 429 semantics and a safe stage trace in the persisted diagnostic if current service behavior permits.
- [x] Update all AutoCardResponse return paths, including model failure, rejected tool submission and success. Add assertions to existing fake-runtime tests for exact ordered stages, zero hidden stages, paid calls and stop reason.
- [x] Run `pytest tests/test_research_auto.py -q` and `npm run build`; expect pass. Commit as `feat: report actual auto-card execution stages`.

## Task 4: Local read-only Swin fixture and zero-network startup

**Files:** `frontend/src/demo/swin-case.json`, `frontend/src/App.vue`, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/style.css`

- [x] Create a fixture from the checked-in Swin source metadata/evidence already represented in `data/processed`; include source ID/version/path, citation-ready evidence locations, one candidate, screening and extraction records with two revisions of each, and a single-paper Markdown report snapshot. Mark every fixture view `预置演示数据`; do not describe it as generated now, gold data, or a multi-paper comparison.
- [x] Remove `onMounted` health fetch. Initialize connection state as unknown and label it `未检测`; update to online/offline only after an explicitly requested live action. Verify the local fixture path uses no API helper, then load it in the browser with the backend stopped; startup and fixture browsing must work without a backend.
- [x] Implement `loadDemoCase()` as a synchronous local import/state assignment. Set a `demoMode` flag and demo source badge; do not use localStorage, API helpers, backend routes, models or ResearchStore. Add `exitDemo()` to clear only demo-owned state and preserve online query/input state.
- [x] In demo mode disable generation, revision, evidence search, agent run, and online comparison controls with visible `只读演示` explanation. Display fixture's one-paper report as a snapshot, not as a comparison report. Add a one-click button beside search.
- [x] Run `npm test -- --reporter=dot` and `npm run build`; manually open the app and verify a cold load + demo load + demo exit with DevTools Network showing zero requests before a live action. Commit as `feat: add offline read-only Swin demo`.

## Task 5: History panel, any-two selector, and evidence-preserving diff UI

**Files:** `frontend/src/api.ts`, `frontend/src/App.vue`, `frontend/src/style.css`, `frontend/src/types.ts`

- [x] Add typed `getResearchHistory(sourceId)` for the history endpoint. Request it when an online candidate becomes active; do not request in demo mode. Keep API failure separate from the global generation error and show a retry action that repeats only the read-only history GET.
- [x] Render screening and extraction histories separately, newest first with time, record type, and `revision_of` reference. With zero or one version, show explicit “暂无历史版本/至少需要两版比较”; do not invent actor attribution.
- [x] Add two selectors restricted to the same type and active paper. Default to the newest two. Call `compareRecords`; render a diff table with status, old/new values, claim status, original quote and evidence location. Show “按出现顺序匹配，需人工确认” for ambiguous duplicates. Keep all duplicate entries visible and in original order.
- [x] Add component-level function tests for default latest-two selection and source/type selector filtering, using the existing Vitest setup. Run `npm test -- --reporter=dot` and `npm run build`; expect pass. Commit as `feat: browse and compare paper record history`.

## Task 6: Error recovery, status messages, and user guide

**Files:** `frontend/src/App.vue`, `frontend/src/style.css`, `README.md`, `docs/p5-web-guide.md`

- [x] Add task status presentation for actual auto-card outcome, ordered stage list, paid calls, prompt/completion tokens, actual cost only when supplied, and fixed stop reason. Missing usage is rendered “服务未提供”; never estimate costs or label synchronous responses as live streaming.
- [x] Map no candidates, no history, model unavailable/timeout/budget exhausted, tool submission rejected, insufficient evidence, history read failure and save failure to distinct messages and safe next actions. Preserve query, selected paper, edits and form state on failure; never auto-retry a generation call. Keep retry only for read-only history.
- [x] Document demo limitations and the source/version for the Swin fixture, live-mode API behavior, history and diff semantics, and safe recovery actions.
- [x] Run `pytest tests/test_research_service.py tests/test_research_api.py tests/test_research_auto.py -q`, `npm test -- --reporter=dot`, and `npm run build`; expect all pass. Re-open the web app and verify online search, history, diff, demo load/exit, model/API failure handling and read-only controls. Commit as `feat: polish research demo status and recovery`.

## Final spec coverage check

- History list/grouping/ordering/corruption isolation: Task 1.
- Same-paper/same-type any-two diff, duplicates, original evidence: Tasks 2 and 5.
- Static source-backed read-only Swin demo, one-paper snapshot, zero API/write: Task 4.
- No automatic `/health`; network failure retains input; no paid auto-retry: Tasks 4 and 6.
- Real bounded stage/use/stop data from synchronous execution: Tasks 3 and 6.
- Error/empty states, browser walkthrough, docs: Task 6.
- Explicitly excluded: P4.6 resealing, paid evaluation, Vision Mamba comparative question set and P6 frozen evaluation.
