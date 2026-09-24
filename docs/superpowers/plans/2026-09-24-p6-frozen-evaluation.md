# P6 Frozen Evaluation: One Run

**Scope:** 8 Swin frozen questions and 32 QASPER validation questions on the P5 product index. Run Dense QA, hybrid-rerank QA, and the verified Agent once per question. No retrial of started tasks and no tuning from results.

## Freeze

- Fix the P5 commit, v2 index fingerprint and manifest, protected evaluation input hashes, QA/Agent prompts and configs, evaluation script, model names, and budgets in `data/processed/evaluation/p6-v1/manifest.json` before opening frozen answers.
- QA variants use `deepseek-v4-pro`, one answer call each, 80 maximum. Agent uses Pro for planner and answer, at most 3 planner + 1 answer calls per task, 160 global maximum.
- All Swin variants use the same explicit `swin_v1` family scope; the Dense row is therefore the scoped Dense implementation. QASPER variants share the same single-paper source filter. Agent can choose additional tools, so its retrieval opportunities are broader than the fixed top-8 QA context.
- Store output in the ignored run directory. Do not copy credentials or raw model requests into Git.

## One execution

- Persist a `started` marker before each of 120 task/variant attempts. Persist completion or failure once; never redispatch a started attempt.
- Keep each task's retrieval output, answer/citations, elapsed time, and usage. Record Agent tool trajectory and stop reason.
- If an API call fails, record it as failed. Do not replace questions or rerun to improve scores.
- A process interruption after a `started` marker consumes the attempt. The report records it as `InterruptedAfterStart` and includes it in the denominator. A returned Agent failure status is also counted as a failed answer.

## Offline report

- Only after execution, read gold answers and score top-8 Swin source-location recall, QASPER paragraph recall and official answer F1, citation validity/coverage, evidence insufficiency handling, elapsed time, and paid calls.
- QASPER official evidence scoring submits a paragraph only when cited chunks cover its full text; partial paragraph hits remain visible in the separate retrieval diagnostics. Citation location coverage is a mechanical proxy, not a judgment that each generated claim is semantically supported.
- Separate automatic metrics from human semantic correctness. Audit a fixed subset manually, preserve disagreements and unsupported claims.
- Bind all raw run files and report to SHA-256; publish summary, methodology and failure cases without modifying the frozen results.

## Delivery boundary

- P6 evaluation is one sealed run. Online deployment, PDF application plan and MP4 demo are independent competition deliverables and remain separately tracked until produced.
