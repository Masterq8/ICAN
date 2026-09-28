# Demo Center Compact Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two redundant text areas and reorganize the demo center into a compact title, action strip and stage navigation layout.

**Architecture:** Keep all Vue state and events intact. Change only `DemoCenter.vue` markup and the demo-center CSS rules, then verify existing interaction tests, builds and responsive rendering.

**Tech Stack:** Vue 3, TypeScript, CSS, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-09-28-demo-center-compact-layout-design.md`

## Global Constraints

- Preserve all existing events, props, button disabled states and href values.
- Remove the intro paragraph and complete footer.
- Stack the mode strip at widths below 900px.
- Do not add state, storage or network behavior.

## Review Focus

- Online and replay text must still switch correctly.
- Static demo must still hide the Agent input link.
- The replay button must preserve disabled and busy labels.
- Collapse must continue hiding the whole panel body.
- No horizontal overflow at narrow widths.

---

### Task 1: Recompose and verify the demo center

**Files:**
- Modify: `frontend/src/components/DemoCenter.vue`
- Modify: `frontend/src/style.css`

**Interfaces:**
- Consumes: existing `demoMode`, `busy`, `staticDemoOnly`, `expanded`, `load-demo` and `toggle-collapse` contracts.
- Produces: the same public component behavior with compact markup and responsive styling.

- [x] Remove the intro copy and footer markup.
- [x] Wrap mode explanation and actions for a horizontal action strip.
- [x] Replace obsolete copy/footer CSS with compact desktop and mobile rules.
- [x] Run `npm test -- --run` and `npm run build` from `frontend`.
- [x] Inspect desktop and narrow layouts in the running browser.
- [x] Commit the finished change.
