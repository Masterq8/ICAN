# ICAN Live Backend Video Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a recording-ready Markdown script for a sub-five-minute ICAN competition video built around two real backend tasks.

**Architecture:** Keep the existing readonly script unchanged as a fallback and create one self-contained live script. The new document owns preflight, exact inputs, timed screen actions, narration, edit markers, truthful result branches, and final acceptance checks.

**Tech Stack:** Markdown, ICAN Vue workspace, FastAPI, Cloudflare Tunnel or localhost, DeepSeek-backed research card and Agent APIs.

**Spec:** `docs/superpowers/specs/2026-09-28-live-backend-video-script-design.md`

## Global Constraints

- Final video duration is at most 5 minutes, with a 4:45 target.
- Record one uninterrupted master and compress only idle model waiting in the final edit.
- Both information-card generation and Agent verification are real online submissions.
- Never show API keys, tunnel tokens, `.env`, raw internal planner text, or frozen-test answers.
- Narration follows actual statuses, usage and citations instead of assuming success.
- The readonly script remains available as the offline fallback.

## Review Focus

- Model latency: the script must mark exact cut points without hiding request or result state.
- Review-required cards: narration must explain human confirmation rather than call the task fully automatic.
- Agent failure or evidence insufficiency: the script must provide truthful replacement wording.
- Source identity: the operator must open both paper evidence and official repository evidence.
- Five-minute limit: each segment needs a target and a hard cut instruction.

---

### Task 1: Create the recording-ready live script

**Files:**
- Create: `docs/contest-live-demo-script.md`

**Interfaces:**
- Consumes: actual labels and online controls in `frontend/src/App.vue`, plus the verified workflow described in `docs/p4-research-guide.md`.
- Produces: one standalone Markdown document that can be followed during capture, narration and editing.

- [x] **Step 1: Write the exact recording setup**

Include backend health checks, browser preparation, secret-hiding rules, the exact research query, the exact Agent query, and the required claim-kind selection.

- [x] **Step 2: Write the continuous-master procedure**

Describe the complete mouse and keyboard sequence from page load through evidence inspection. Mark the two model waits but do not allow the operator to stop the master recording.

- [x] **Step 3: Write the 4:45 timed narration**

Use a table with time, screen action, exact narration and editing note. Ensure the contest-required Agent request, analysis, decision, tool collaboration and feedback are visible.

- [x] **Step 4: Add truthful result branches**

Provide ready-to-read replacement lines for completed, review-required, insufficient-evidence, blocked and failed terminal states.

- [x] **Step 5: Add editing and acceptance checklists**

Require explicit wait-compression captions, task/result continuity, paper and source citations, readable zoom, audible narration and a final duration below five minutes.

- [x] **Step 6: Validate the document**

Run:

```powershell
rg -n "TODO|TBD|API_KEY|sk-|Tunnel Token" docs/contest-live-demo-script.md
rg -n "从原文生成|代码前置条件|运行核查|真实在线执行|等待过程已压缩" docs/contest-live-demo-script.md
```

Expected: the first command finds only explicit prohibitions and no secret value or unfinished placeholder; the second finds every required online-flow marker.

- [x] **Step 7: Commit**

```powershell
git add docs/contest-live-demo-script.md docs/superpowers/specs/2026-09-28-live-backend-video-script-design.md docs/superpowers/plans/2026-09-28-live-backend-video-script.md
git commit -m "docs: add live backend contest video script"
```
