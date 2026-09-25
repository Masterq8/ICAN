# ICAN Video Demo Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Add a guided five-step demo center and display real, privacy-bounded Agent traces for both the existing read-only Swin replay and explicitly submitted online runs.

**Architecture:** Keep the existing Vue/FastAPI workbench as the product surface and add a small guide component that links into its current sections. Preserve internal Agent records for evaluation, but project them into a separate public response DTO at the API boundary. Ship a curated, read-only trace snapshot derived from a completed non-P6 Swin development run; keep the response display reusable between replay and online execution.

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Vite, Vitest, FastAPI, Pydantic, pytest.

---

## File map

- `ican/agent/schema.py` — define the API-safe Agent trajectory event and response models; leave the internal `AgentResponse` contract intact.
- `ican/agent/service.py` — add validated tool arguments and turn number to internal tool events so the API can make truthful summaries.
- `ican/agent/public_response.py` — project internal responses to allowlisted public fields; summarize arguments/results deterministically and with length bounds.
- `ican/api/app.py` — return the public DTO from `POST /v1/agent/run`.
- `tests/test_agent_api.py` — prove the public contract excludes planner action, tool-call IDs and raw tool output while preserving actual order/status.
- `tests/test_agent_service.py` — verify internal tool event argument recording and turn association.
- `frontend/src/types.ts` — model the public trajectory and nested QA citations accurately.
- `frontend/src/agentTrace.ts`, `frontend/src/agentTrace.test.ts` — format known event/status labels and test unknown or missing values without inventing facts.
- `frontend/src/components/AgentTrace.vue` — accessible timeline, actual status/use/answer/citations and evidence-open events.
- `frontend/src/components/DemoCenter.vue` — the five-stage guide, visible execution-mode label and links into existing workbench sections.
- `frontend/src/demo/swin-agent-trace.json` — safe replay snapshot from the cited completed non-P6 Swin development run.
- `frontend/src/App.vue`, `frontend/src/style.css` — add the entry, wire replay and online Agent result to shared components, and style desktop/mobile states.
- `task_plan.md` — record the demo-center and trace UI delivery separately from MP4/video and application-plan deliverables.

## Task 1: Build a safe public Agent response

**Files:** `ican/agent/schema.py`, `ican/agent/service.py`, `ican/agent/public_response.py`, `ican/api/app.py`, `tests/test_agent_api.py`, `tests/test_agent_service.py`.

- [x] Add `PublicAgentEvent` with only `event`, `turn`, `tool`, `parameter_summary`, `status`, `result_summary`, and `cached`; constrain values and lengths with Pydantic.
- [x] Add `PublicAgentResponse` by mirroring the client-required Agent fields and typing `trajectory` as `list[PublicAgentEvent]`; do not replace the internal `AgentResponse` model used by evaluation.
- [x] Add `turn` and already schema-validated `arguments` to internal tool events in `AgentService.run`:

```python
response.trajectory.append(
    {
        "event": "tool",
        "turn": turn + 1,
        "name": name,
        "arguments": arguments if isinstance(arguments, dict) else {},
        "tool_call_id": call["id"],
        "result": result,
        "cached": cached,
    }
)
```

- [x] Implement `to_public_agent_response(response)` to map planner events to `{event: "planning", turn}` only; never copy `action`, planner `content`, or `tool_call_id`.
- [x] Restrict public tool names to the current Agent tool registry. Summarize only allowlisted argument fields: search query and scope, evidence-read location, config field/path, calculation expression, and item counts for claim/record/report submissions. Unknown arguments become `"参数已按安全规则省略"`.
- [x] Summarize parsed tool results deterministically: evidence count for search/read, scalar result for calculation, claim status counts for verification/submission, answer status for generation; errors become a bounded generic failure message. Do not include raw result JSON or evidence body text.
- [x] Change only the FastAPI route to declare `response_model=PublicAgentResponse` and return `to_public_agent_response(await service.run(request))`.
- [x] Add a test with a fake internal response containing planner private text, an opaque call id, unsafe extra arguments, a long raw result and two ordered tool calls. Assert the HTTP JSON has order/status but none of those private fields or full tool output.
- [x] Initialize the per-call `arguments` value to `{}` before parsing so malformed JSON still produces a valid internal event; add a service assertion that fake-tool execution records validated arguments and planner turn internally.
- [x] Add table-driven projector assertions for completed, cached, validation-error, malformed-result, unknown-tool and length-bounded events.
- [x] Run `python -m pytest tests/test_agent_api.py tests/test_agent_service.py -q` and confirm PASS (32 passed).

## Task 2: Define the frontend trace view model

**Files:** `frontend/src/types.ts`, `frontend/src/agentTrace.ts`, `frontend/src/agentTrace.test.ts`.

- [x] Add TypeScript types matching `PublicAgentEvent` and the API’s nested `QAResponse.citations[].evidence` structure. Change `actual_cost_usd` to `number | null` and add `planner_model` / `answer_model` if returned by the public DTO.
- [x] Implement deterministic Chinese labels for known Agent statuses, stop reasons, event kinds, tool names and event statuses. Preserve unknown backend codes verbatim as an “其他状态” value rather than turning them into success.
- [x] Create a pure `displayTrajectory(events)` mapper that preserves event order, bounds strings at the API’s maximum, and does not infer events from `workflow_stages` or the answer.
- [x] Add Vitest cases for planner turns, completed/cached/failed tools, unknown tool/status codes, empty trace, and citation evidence extraction.
- [x] Run `npm test -- src/agentTrace.test.ts` from `frontend/` and confirm PASS.

## Task 3: Create the reusable Agent trace and demo-guide components

**Files:** `frontend/src/components/AgentTrace.vue`, `frontend/src/components/DemoCenter.vue`, `frontend/src/style.css`.

- [x] Build `AgentTrace.vue` with required `response` and optional `loading`/`mode` props and an `open-evidence` event carrying the existing `Evidence` type. Render actual status, stop reason, usage, ordered tool timeline, final answer and citation buttons.
- [x] While `loading` is true, show only “请求已提交，等待服务端返回 Agent 轨迹”; do not render in-flight fake steps, percentage, or simulated timestamps.
- [x] When the response has no trace, display “本次服务未返回详细轨迹” and keep the real answer/status visible. In replay mode show “预置演示数据 · 只读”.
- [x] Build `DemoCenter.vue` as a compact five-stage guide: context, paper filtering, information card/history, Agent/tools, evidence/conclusion. Use anchor links to existing `#demo`, `#papers`, `#card`, `#reproduction`, and the evidence panel at `#evidence`; emit `load-demo` from its one-click action.
- [x] Keep the current academic navy/teal/cream visual language. Add a horizontal desktop stage rail, clear numbered focus states, and a horizontally scrollable mobile rail; honor `prefers-reduced-motion` and visible keyboard focus.
- [x] Add accessible headings, ordered-list semantics for trace items, and `aria-live="polite"` only for the actual busy status.
- [x] Run `npm run build` from `frontend/` and confirm PASS before wiring global state.

## Task 4: Add a truthful Swin replay and connect the existing workbench

**Files:** `frontend/src/demo/swin-agent-trace.json`, `frontend/src/App.vue`, `frontend/src/style.css`.

- [x] Create the replay snapshot from `data/processed/agent/p4-v1/tasks/b0d9bb2c0b87499a917d8749f814fddd.json`, selecting only public fields. Record source task ID, source artifact SHA-256 `4D4A129EBC7D6CCFE03EFDF729362F7D93A5F7F7E25EA709C0FEA4D0B02499DA`, query, pinned Swin source version, actual models, actual stop/status/usage, selected tool order and answer citations.
- [x] Preserve actual event order from the saved trajectory; do not include planner raw actions, raw results, API credentials, evaluation artifacts or source task internals in the shipped JSON.
- [x] Confirm the replay query is not identical to any question in `data/eval/swin_test.jsonl`. The source task is a completed development run, status `completed`, stop reason `final_answer_generated`, with `search_evidence` and `gen_answer` calls.
- [x] Add `DemoCenter` to the sidebar and page before the workbench. Give the existing evidence panel `id="evidence"`. Clicking the guide button invokes the existing local `loadDemoCase()` and assigns the imported trace snapshot to `agentResult`; it must not call `fetch`, model APIs, ResearchStore or browser storage.
- [x] Replace the inline Agent result block with `AgentTrace`; for online mode pass the live API result and route its evidence events into the existing evidence panel. Keep the existing explicit “运行核查” action as the only way to submit the paid request.
- [x] Update the replay banner/button text and add a clear path back to the online workbench without discarding the pre-replay live state.
- [x] Run `npm test` and `npm run build` from `frontend/`; run `python -m pytest tests/test_agent_api.py tests/test_agent_service.py -q` from repository root.

## Task 5: Rendered browser QA and delivery notes

**Files:** `task_plan.md` (only if implementation acceptance passes).

- [x] Start the existing Vite dev server at `127.0.0.1` and verify the desktop flow: open `#demo`, load read-only Swin replay, jump to information history, open an Agent citation in the evidence panel, and exit replay to restore online state.
- [x] Verify no network request occurs when loading, browsing, or exiting replay; verify no paid request occurs until “运行核查” is clicked. For online behavior, use a mocked/local test response rather than a new paid model run.
- [x] Verify 1440×900 desktop and 390×844 mobile layouts, browser console, keyboard focus, reduced-motion behavior and page identity. Review temporary screenshots through the browser UI and keep generated screenshots out of the repository.
- [x] If the Browser plugin is absent, use the available local Playwright installation; do not add a new frontend dependency just for this task.
- [x] Run the targeted Python and frontend tests once more after browser fixes; update the relevant P6 competition-deliverable row in `task_plan.md` to mark only the web presentation path complete, leaving the MP4 video and application plan pending.

## Task 6: Lock the Cloudflare Pages static demo profile

**Files:** `frontend/src/App.vue`, `frontend/src/components/DemoCenter.vue`, this design and plan.

- [x] When `VITE_DEMO_ONLY=true`, load the fixed Swin fixture at startup, label the page as a public read-only demo, hide the exit-to-live and Agent-input links, and disable online query and Agent controls.
- [x] Keep the default local build unchanged so developers can still switch between replay and the live backend.
- [x] Build and inspect the Pages profile in the Codex in-app browser; confirm the replay appears on first load, online controls are disabled, citation navigation works, and no `/v1` request occurs during load or viewing.
- [x] Re-run frontend tests (10 passed), default/local and Pages production builds, targeted backend tests (33 passed), and `git diff --check`.
- [x] Complete the final pre-push code review; the static profile hides Agent submission controls and preserves the replay trace.

## Non-negotiable boundaries

- Do not alter `data/eval/swin_test.jsonl`, `data/eval/swin_eval_manifest.json`, P6 manifests/reports, frozen metrics or sealed results.
- Do not make a paid model call for fixture creation or browser validation; use the completed saved development run identified above.
- Do not add SSE/WebSocket, simulated streaming, automatic retry, planner chain-of-thought, raw tool output or browser persistence to replay mode.
- Keep existing internal Agent trace/persistence behavior available to evaluation; only the public HTTP projection and user-visible replay snapshot are reduced.
