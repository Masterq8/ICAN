# Vision Mamba Evidence and Swin Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an independently validated Vim development question set and a source-backed four-dimension comparison with Swin-T.

**Architecture:** Keep all gold labels outside retrieval corpora. Bind question claims to stable `VPxx`/`VRxx` evidence IDs, physical PDF pages or pinned repository lines, and current v2 index chunk IDs. A read-only validator checks these bindings before the comparison card is marked complete.

**Tech Stack:** Python 3.11 standard library, existing parsed PDF/chunk JSONL, fixed Git repositories, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-24-vim-evidence-comparison-design.md`

## Global constraints

- Vim PDF SHA-256: `15c3ccf7340a412e6ce408526c03a67e412d9bb4958e6c0bfe310394b6337444`; repository HEAD: `dd0358ad1e42701f22afbefa0717cc8825cf9f45`.
- Swin repository HEAD: `f82860bfb5225915aca09c3227159ee9e1df874d`; existing `data/eval/swin_*` files remain unchanged.
- PDF page means physical one-based page; repository lines mean fixed commit file lines.
- No paid model calls or P6 frozen evaluation in this plan.

## Review focus

- A Vim evidence chunk from `seg/`, `det/`, `Hier-Vim`, or the bundled unrelated Swin code must not silently support a Vim-Ti answer.
- A code locator whose line range does not overlap the indexed chunk must fail validation.
- A paper page number that disagrees with the indexed chunk or parsed page must fail validation.
- A question referencing a missing evidence ID or omitting one of its gold claims' citations must fail validation.
- Vim-Ti and long-sequence `†` results must remain separate; Swin's paper value and the Vim appendix's Swin citation must not be merged.

## Task 1: Evidence map and read-only validator

**Files:** Create `data/eval/vision_mamba_evidence.json`, `scripts/validate_vision_mamba_dev.py`, `tests/test_vision_mamba_dataset.py`.

**Interfaces:** Validator exposes `validate(root: Path) -> list[str]` and `main() -> int`; each evidence entry has `id`, `source`, `source_path`, `source_version`, `page` or `lines`, `chunk_id`, `anchor`, `supports`. The question set from Task 2 uses `required_evidence` referencing those IDs.

- [x] Select 24 focused Vim paper/code evidence entries from physical PDF pages 1, 4–8, 13–14 and fixed source files; record exact v2 `chunk_id` and short source anchor. Table rows were checked against PDF pages.
- [x] Write a failing test that changes one evidence page, code line range, or chunk source and expects a specific validation error. Confirm the initial failure was due to absent validation.
- [x] Implement validation: assert pinned PDF and chunk hashes, repository HEAD and committed source content; load current Vim v2 chunks keyed by `chunk_id`; validate exact source path/version/type, page or line containment, normalized anchor in both chunk and raw page/file; reject duplicate IDs and cross-variant paths. Return collected errors and make CLI nonzero on any error.
- [x] Add tests for valid map, mutations and fixed-pin integrity; rerun targeted pytest and `python scripts/validate_vision_mamba_dev.py` until both pass. New implementation files are committed together after review.

## Task 2: Eight Vim development questions

**Files:** Create `data/eval/vision_mamba_dev.jsonl`; extend validator tests for question integrity.

**Interfaces:** Each question follows the Swin JSONL keys: `id`, `split`, `question`, `scope`, `category`, `difficulty`, `answer_status`, `gold_answer`, `gold_claims`, `required_evidence`, `supporting_evidence`, `grading_points`, `leakage_group`, `annotation_notes`.

- [x] Add eight independent Vim-Ti questions covering patch tokens, middle class token, per-block BiMamba v2 versus the outer `if_bidirectional` branch, 16/8 long-sequence patching, theoretical complexity, ImageNet training, 76.1 versus 78.3†, and Hier-Vim variant distinction. Each gold claim cites necessary IDs only and states conditions in its own text.
- [x] Extend the validator to check exactly eight unique development IDs, unique leakage groups, known evidence IDs, nonempty gold claims, and that `required_evidence` covers every claim citation. Add a failing bad-reference test, then make it pass.
- [x] Run validator and focused pytest. Confirm none of the new gold files appear in `configs/chunking/v2.json` or `configs/indexing/v2.json` retrieval inputs. New implementation files are committed together after review.

## Task 3: Four-dimension comparison card and plan sync

**Files:** Create `docs/vision-mamba-swin-comparison.md`; modify `docs/p5-dual-vision-guide.md`, `task_plan.md`, `progress.md`.

**Interfaces:** Comparison rows refer to Vim `VPxx`/`VRxx` in Task 1 and existing Swin `Pxx`/`Rxx` in `data/eval/swin_evidence.json`. Each dimension gives source-backed facts, a comparability judgment, and a limitation.

- [x] Compare fixed Vim-Ti and Swin-T architecture, attention/SSM complexity with symbols defined separately, 224 input patch/sequence counts and fixed-size assertions, and ImageNet-1K training/results. Show exact sources, v2 chunk IDs, PDF pages/code lines.
- [x] Explicitly distinguish Vim-Ti, Vim-Ti†, Hier-Vim-T, and Swin-T; note 81.3 in Swin's own paper versus 81.2 in Vim appendix/official README as source-specific values. No global performance ranking or speed extrapolation.
- [x] Update guide and root plan to mark the local P5 experience and Vim evidence/comparison deliverables complete while keeping P5 overall in progress. Online deployment/video remain in P6. Append progress with source checks and test outcomes.
- [x] Run validator, targeted pytest, `git diff --check` on tracked task files, and hash comparison against the committed Swin frozen files. Inspect new documents for unsupported numeric claims and broken local references. Commit separable new files only; shared pre-existing edits remain in the working tree.

## Final gate

- Validator and tests pass with no paid calls.
- Eight questions have fully bound evidence; comparison card covers all four dimensions and uncertainty.
- Swin frozen dataset hashes remain equal to committed baseline; P6 is still pending.
