# P2.6 Baseline Evaluation Implementation Plan

> Current-session inline execution with executing-plans. User has authorized the P2.6 scope; budget question is pending for batch generation only.

**Goal:** Reproducible Swin dev and QASPER validation baselines with separated retrieval, answer and citation metrics.

**Architecture:** Fixed query-only cases → one dense retrieval snapshot → budgeted PaperQA2 configurations → offline gold scorer → semantic audit and report. Official QASPER evaluate is reused with attribution.

**Tech Stack:** Existing BGE-M3/Qdrant, PaperQA2 2026.8.12, DeepSeek OpenAI-compatible runtime, Python3.11, official QASPER evaluator.

## 1. Data isolation and metric contracts

Files: ican/evaluation/data.py, metrics.py; tests/test_evaluation_metrics.py; third_party/qasper.

- [x] Vendor official evaluator.py and LICENSE at afd0fb96bf78ce8cd8157639c6f6a6995e4f9089; record normalized file hash.
- [x] Write failing tests for union interval coverage, same-page proxy, additional_path, repeated sources, and official multiple-reference F1. Run `python -m pytest tests/test_evaluation_metrics.py -q` before implementation.
- [x] Add query-only Case(id,dataset,split,question,collection,filters), no gold fields; load fixed12 Swin dev, first3 train question IDs sorted, and32 validation cases. Validate file SHA using existing manifests before reading allowed gold. Swin frozen test is hash-only.
- [x] Implement `intervals_cover(targets, intervals)` with a moving cursor over merged ranges; gaps fail. Score repository line completeness separately from page/line locator hits. QASPER full unit coverage unions chunk char_start/end against non-whitespace corpus positions.
- [x] Convert each official annotation: Unanswerable / joined extractive spans / free_form_answer / Yes / No, plus original evidence text. Use official evaluate for maxima over references; remove only citation tokens from predictions and preserve raw responses.

## 2. Retrieval snapshots and bounded generation

Files: ican/evaluation/runner.py; scripts/evaluate_baseline.py; tests/test_evaluation_runner.py.

- [x] Test global budget deduction before model dispatch, existing started items not repeated, gold excluded from prompt, default serializer source limit, timeout/failure accounting, and no-paper leakage for QASPER.
- [x] CLI `retrieval --run-dir data/processed/evaluation/p26-v1`: record query-only requests, Top8 SearchResponse, input hashes, index, source versions and elapsed_seconds. One shared evidence service, no generation.
- [ ] CLI `generate --run-dir ... --max-calls N --variants adapter,paperqa-default`: reuse stored search results, do not reretrieve from gold. Append started journal before SDK call and completed/error after; each dispatch consumes one budget slot. Resume matches all input/config/prompt/model fingerprints and skips every started key.
- [x] Adapted eval Settings changes only answer language instruction (eval version separate from productionv2); upstream-default uses default prompts/serializer/source limit, disables only automatic retrieval and auxiliary calls for equal single-call budget. Registry is pruned to IDs actually serialized.
- [ ] Execute train first, then Swin dev, then QASPER validation using frozen config. Each request 1536tokens/90seconds, no retry/fallback. No generation until user budget reply.

## 3. Reports and semantic review

Files: scripts/evaluate_baseline.py report; docs/p2-baseline-report.md; ignoredrun/audit.jsonl.

- [x] Report K1/3/5/8 locator and strict-range metrics; QASPER official answer/evidence F1, complete-unit recall, n/denominators, no-gold cases and errors. Aggregate by dataset+variant, keep train separate. Incomplete runs are labelled incomplete; failures receive0 in answer metrics, not silently excluded.
- [ ] Inspect all generated answers against grading_points/reference answers and cited evidence, record semantic judgments with explicit reasons; automatic gold overlap is labelled proxy. Answer status semantics reviewed separately from API reliability statuses.
- [ ] Report models, prompt hashes, index, configuration differences, call counts/tokens, timing, unknown cost, failures and next P3 priorities. Do not claim an unrun full PaperQA2 Agent baseline.

## 4. Verification and handoff

- [x] Run targeted/full pytest, scoped Ruff excluding vendoredsource, pip check, protected61 hashes and staged credential scan. Request independent read-only code review, fix important findings.
- [ ] Update task_plan/progress/findings, requirements/roadmap/reuse notes and problem log. Commit locally on codex/p2-6-evaluation; no push requested.

## Current checkpoint (in_progress)

2026-09-17: all47 local dense retrieval cases complete. Final p26-v2 reuses the checked preflight ranking with original provenance and sealed SHA. Swin locator@8=0.326389; repository fullrange@8=0.083333. QASPER validation complete paragraph@8=0.784946 on31 applicable questions; all32 questions retained. 136 tests passed, 1 Windowspermission skip;13 evaluation tests, pip check and scoped Ruff passed. Independent code review resolved mutable/resealable snapshot, interrupted-denominator, and no-evidence applicability findings.

Generation implementation is complete and tested offline, but its CLI execution acceptance remains unchecked. No batch generation has been sent (0calls); user budget reply pending (94bothvariants /47adapter /localretrieval only). Real answers, semantic audit, final generation comparison and P2.6 completion remain pending. Current records/docs are saved locally; status stays in_progress.
