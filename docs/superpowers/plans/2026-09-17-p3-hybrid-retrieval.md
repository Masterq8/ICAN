# P3 Hybrid Retrieval Implementation Plan

> Current-session inline execution with executing-plans; user has authorized P3. Review major work independently via requesting-code-review. No fresh design/execution permission needed.

**Goal:** Reduce wrong Swin-family results and recover code/configuration evidence, with measured comparison against preserved P2.6.

**Architecture:** Verified existing chunks → deterministic scope/query terms → dense and BM25 candidates → RRF → local reranker → bounded structural context selection → unchanged evidence DTO/PaperQA2 adapter. All channels enforce user filters.

**Tech Stack:** Python3.11, rank-bm25, existing BGE-M3/Qdrant, Transformers FP16 BGE-reranker-v2-m3, FastAPI, PaperQA2, official QASPER evaluator.

## 1. Lexical retrieval and model scope

Files: create ican/retrieval/lexical.py, scope.py, policy.py; tests/test_hybrid_retrieval.py; configs/retrieval/v1.json.

- [x] Define `tokens(text: str) -> list[str]`, preserving dotted/underscore identifiers and splitting them into component words; Chinese character/bigram tokens. `expand_query(query: str) -> list[str]` records deterministic CLI/terminology aliases, no model or gold use.
- [x] Test explicit family override, multi-family ambiguity, source/path intersection, exact YAML field, CLI identifier, and stable duplicate-free fusion. Example: `assert resolve_family('Swin V2', 'swin_v1', 'auto')[0] == 'swin_v2'`; forbidden SimMIM candidate cannot reappear during expansion.
- [x] Implement `LexicalIndex(rows)` with sorted unique chunk IDs and BM25Okapi(k1=1.5,b=.75), positive IDF; query-specific eligible rows. `fuse(rankings, k=60)` sums1/(k+rank), ties by stable chunk ID.
- [x] Run `python -m pytest tests/test_hybrid_retrieval.py -q`; inspect no-gold query behavior and record corpus/config fingerprint.

## 2. Pinned local reranker

Files: create ican/retrieval/reranking.py, scripts/prepare_reranker.py, configs/reranking/v1.json, data/catalog/reranker-bge-v2-m3.json.

- [x] Prepare only pinned tokenizer/config/README/safetensors; compare size plus LFS SHA or git blob SHA, save actual SHA ledger with Apache-2.0 and official source.
- [x] Load `AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)` and equivalent classification model, FP16 CUDA batch2. Pair window1536 with explicit truncation count; logits finite, one scalar each, no calibrated confidence claim.
- [x] Test nonfinite/wrong-count outputs and fail closed if model missing; health endpoint remains lazy. Download/run command: `python scripts/prepare_reranker.py`.

## 3. Hybrid service and API

Files: modify ican/retrieval/schema.py, service.py, ican/api/app.py; create ican/retrieval/hybrid.py; extend tests/test_hybrid_retrieval.py and API tests.

- [x] Add strategy/family request fields with dense default; response trace default empty. Add bounded internal dense candidates with eligible chunk IDs before vector ranking, preserve original dense route.
- [x] Implement HybridEvidenceService.search(SearchRequest) with verified chunk registry,40/channel,48rerank candidates and RRF. Family inference explicit in trace; unknown collection fails before model load.
- [x] Structural selection returns only existing chunks, exact original text/location/version/review flags; fragments bounded and all scopes intersected. Trace records every selected ID and scoring role. Dev calibration adds YAML BASE closure and query-named defaults/functions; no dynamic execution.
- [x] App factory uses lazy hybrid wrapper and still allows injected offline services. PaperQA2 uses same result contract and own8chunk/18kchar budget; no extra summary/embedding calls.
- [x] Run all retrieval/QA/API tests, inspect source scope, concurrency, health laziness and unchanged dense semantics.

## 4. Retrieval ablations

Files: create scripts/evaluate_retrieval_strategies.py, docs/p3-retrieval-report.md; new ignored data/processed/evaluation/p3-v1.

- [x] Use fixed query-only Case inputs, same collections/filters, Top8. Five dispatched strategies plus hybrid_rerank_raw derived from the same scoring pass to isolate structural selection. Parameters fixed after dev/train check and before validation.
- [x] Save input/source/model/config hashes, actual index fingerprint/identity/manifest SHA, requests, traces, raw evidence and elapsed time; sealed results reusable only when hashes match. Preserve P2.6 files untouched.
- [x] Reuse existing score_swin / score_qasper_retrieval for K1/3/5/8; distinguish page locator vs full range, and applicable gold evidence denominators. Keep train/dev/observed validation separate.
- [x] Complete 282 records in `p3-final-v3`; retain calibration and functional-fix run history. Report gains/regressions, configuration-chain examples and trace; no generation for all five strategies.

## 5. Answer/citation acceptance

- [x] Compare improved evidence on same PaperQA2 adapter/prompt/model against preserved P2.6 baseline; 47 single-call answers in `p3-qa-v1`, no retries. Independently verify final retrieval prepares the same 47 generation inputs; do not reuse old semantic judgments for new answers.
- [x] Review all 47 new answers against allowed rubric/reference and actual cited spans. Preserve data ambiguity and reject wrong model/experiment attribution. Frozen Swin test remains hash-only.

## 6. Review, documents, local completion

- [x] Independent read-only code review required by requesting-code-review; fix integrity/filter/model/index issues and both ASCII field boundaries before final run.
- [x] Complete full178 tests (1 Windows permission skip), scoped Ruff/format, protected61 plus P2.6 snapshot SHA checks and staged credential scan; no dependency changes.
- [x] Update task_plan/progress/findings, requirements/reuse/roadmap/problem log; local completion on codex/p3-hybrid-retrieval. Do not automatically start P4, remind user before Agent planning.
