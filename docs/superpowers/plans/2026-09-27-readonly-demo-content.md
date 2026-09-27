# Complete Readonly Swin Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse two-field Swin readonly fixture with a complete, source-bound research card, revision history, report, and evidence experience that works without backend requests.

**Architecture:** Keep curated demo facts in `swin-case.json`, while a focused TypeScript module validates the fixture contract and hydrates claim evidence before Vue renders it. `App.vue` remains the orchestration entry and continues to reuse the existing field table, history diff, evidence inspector, report, and Agent replay components.

**Tech Stack:** Vue 3, TypeScript, Vite, Vitest, static JSON fixtures.

---

## File map

- Create `frontend/src/demoFixture.ts`: typed readonly-fixture validation and evidence hydration.
- Create `frontend/src/demoFixture.test.ts`: contract tests for complete fields, evidence bindings, revisions, and the 81.2/81.3 conflict.
- Modify `frontend/src/demo/swin-case.json`: complete Swin research card, evidence set, two revisions, and report.
- Modify `frontend/src/App.vue`: validate and hydrate the fixture through the focused module.
- Modify `docs/p5-web-guide.md`: describe the complete offline walkthrough.
- Modify `docs/problem-solution-log.md`: record the sparse-fixture defect and verified resolution.

### Task 1: Lock the readonly fixture contract with failing tests

**Files:**
- Create: `frontend/src/demoFixture.test.ts`
- Create: `frontend/src/demoFixture.ts`

- [x] **Step 1: Write the failing fixture contract test**

Create a test that imports `swin-case.json` and requires all visible field names, resolvable evidence, a valid two-version chain, and separate conflicting result sources:

```ts
import { describe, expect, it } from 'vitest'
import fixture from './demo/swin-case.json'
import { hydrateAndValidateDemoFixture, requiredDemoFields } from './demoFixture'

describe('readonly Swin demo fixture', () => {
  it('covers every visible card field with clickable source evidence', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)
    const latest = demo.history.extraction[0]
    expect(new Set(latest.fields.map(field => field.name))).toEqual(new Set(requiredDemoFields))
    expect(latest.fields.every(field => field.claims.length > 0)).toBe(true)
    expect(latest.fields.flatMap(field => field.claims).every(claim => claim.evidence.length > 0)).toBe(true)
  })

  it('keeps paper 81.3 and repository 81.2 as separate sourced results', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)
    const results = demo.history.extraction[0].fields.filter(field => field.name === 'result')
    expect(results.map(field => field.value)).toEqual(expect.arrayContaining([
      '论文 Table 1(a)：Swin-T 在 ImageNet-1K、224×224 下 top-1 为 81.3%',
      '官方仓库模型表：对应 Swin-T checkpoint 的 top-1 为 81.2%',
    ]))
    expect(new Set(results.flatMap(field => field.claims.flatMap(claim => claim.evidence.map(item => item.source.source_type))))).toEqual(new Set(['paper', 'documentation']))
  })

  it('preserves stable revision chains', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)
    expect(demo.history.screening[0].revision_of).toBe(demo.history.screening[1].record_id)
    expect(demo.history.extraction[0].revision_of).toBe(demo.history.extraction[1].record_id)
  })
})
```

- [x] **Step 2: Run the test and verify the sparse fixture fails**

Run: `cd frontend; npm test -- --run src/demoFixture.test.ts`

Expected: FAIL because `demoFixture.ts` is absent or because the latest fixture does not cover all nine fields.

- [x] **Step 3: Add the focused validator and hydrator**

Implement `requiredDemoFields` and `hydrateAndValidateDemoFixture`. It must reject missing fields, unresolved evidence IDs, non-demo labels, fewer than two revisions, and broken `revision_of` links; then return history records with evidence objects attached:

```ts
import type { Candidate, ResearchHistory, ResearchRecord } from './types'

export const requiredDemoFields = [
  'task', 'model', 'dataset', 'input_setting', 'training',
  'metric', 'result', 'limitation', 'code_availability',
] as const

export interface DemoFixture {
  label: string
  query: string
  candidate: Candidate
  history: ResearchHistory
  report: string
}

function hydrateRecord(record: ResearchRecord, candidate: Candidate): ResearchRecord {
  const byId = new Map(candidate.evidence.map(item => [item.chunk_id, item]))
  const attach = <T extends ResearchRecord['claims'][number]>(verdict: T): T => {
    const evidence = verdict.claim.evidence_ids.map(id => byId.get(id))
    if (evidence.some(item => !item)) throw new Error('Readonly demo references missing evidence')
    return { ...verdict, evidence } as T
  }
  return {
    ...record,
    claims: record.claims.map(attach),
    fields: record.fields.map(field => ({ ...field, claims: field.claims.map(attach) })),
  }
}

export function hydrateAndValidateDemoFixture(raw: unknown): DemoFixture {
  const fixture = raw as DemoFixture
  if (!fixture.label.includes('预置演示数据')) throw new Error('Readonly demo label is missing')
  if (fixture.history.screening.length < 2 || fixture.history.extraction.length < 2) {
    throw new Error('Readonly demo requires two history versions')
  }
  const latest = fixture.history.extraction[0]
  const names = new Set(latest.fields.map(field => field.name))
  if (requiredDemoFields.some(name => !names.has(name))) {
    throw new Error('Readonly demo card is incomplete')
  }
  if (fixture.history.screening[0].revision_of !== fixture.history.screening[1].record_id ||
      latest.revision_of !== fixture.history.extraction[1].record_id) {
    throw new Error('Readonly demo revision chain is invalid')
  }
  return {
    ...fixture,
    history: {
      screening: fixture.history.screening.map(record => hydrateRecord(record, fixture.candidate)),
      extraction: fixture.history.extraction.map(record => hydrateRecord(record, fixture.candidate)),
      diagnostics: [],
    },
  }
}
```

- [x] **Step 4: Run the test and confirm it now fails only on sparse fixture content**

Run: `cd frontend; npm test -- --run src/demoFixture.test.ts`

Expected: FAIL with `Readonly demo card is incomplete`.

- [x] **Step 5: Commit the contract module and failing test**

Run:

```powershell
git add frontend/src/demoFixture.ts frontend/src/demoFixture.test.ts
git commit -m "test: define complete readonly demo contract"
```

### Task 2: Replace the sparse Swin fixture with complete source-bound content

**Files:**
- Modify: `frontend/src/demo/swin-case.json`
- Test: `frontend/src/demoFixture.test.ts`

- [x] **Step 1: Expand candidate evidence using fixed sources**

Add bounded, continuous excerpts for the following source locators, preserving the fixed paper and repository versions:

```text
paper page 1: task coverage (classification, detection, segmentation)
paper page 2: shifted-window connection mechanism
paper page 5: Swin-T architecture settings
paper page 6 Table 1(a): ImageNet-1K top-1 81.3
paper page 9 Appendix A2.1: ImageNet training setting
config YAML lines 1-9: patch4/window7/224 and architecture dimensions
models/swin_transformer.py lines 448-475: PatchEmbed projection and input assertion
models/build.py lines 34-52: build_model entry
README.md lines 110-118: checkpoint table top-1 81.2
```

Every evidence object must have a unique stable `chunk_id`, fixed `source_version`, and page or line location. Paper snippets use `source_type: "paper"`; Python implementation snippets use `"code"`, YAML uses `"config"`, and the repository README uses `"documentation"`.

- [x] **Step 2: Build the two extraction versions**

Keep the older version intentionally partial with `task`, `model`, one `result`, and `code_availability`. Make the latest version contain these exact field groups:

```text
task x1
model x1
dataset x3: ImageNet-1K, COCO, ADE20K
input_setting x1: 224×224, 4×4 patch, 7×7 window
training x1: source-bounded ImageNet-1K setting
metric x1: top-1 accuracy
result x3: shifted-window connection, paper 81.3, repository 81.2
limitation x1: fixed PatchEmbed input-size assertion
code_availability x2: Swin-T YAML and model build/implementation entry
```

Use `supported` only for continuous source quotes. Use `requires_review` for Chinese synthesis across multiple facts. Bind every claim to at least one evidence ID in `candidate.evidence`.

- [x] **Step 3: Update the report to mirror the latest card**

The Markdown report must contain: source scope, task and architecture, datasets, input/training setup, top-1 metric, the separate 81.3/81.2 values, reproduction limitation, code entry points, and the statement that the snapshot is curated demo data rather than a live model result.

- [x] **Step 4: Run the fixture tests**

Run: `cd frontend; npm test -- --run src/demoFixture.test.ts`

Expected: fixture contract tests PASS, including the negative quote-binding case.

- [x] **Step 5: Commit the complete fixture**

Run:

```powershell
git add frontend/src/demo/swin-case.json
git commit -m "feat: fill readonly Swin demo with sourced research fields"
```

### Task 3: Integrate validated fixture hydration into the Vue entry

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/demoFixture.test.ts`

- [x] **Step 1: Replace the inline evidence enrichment**

Import and call the validated fixture helper:

```ts
import { hydrateAndValidateDemoFixture } from './demoFixture'

function loadDemoCase() {
  // preserve the existing live-state snapshot logic
  const fixture = hydrateAndValidateDemoFixture(demoFixture)
  // preserve existing demo state assignments
  const demoHistory = fixture.history
  // remove the old inline enrichEvidence mapper
}
```

All existing readonly guards, static-only behavior, Agent replay loading, selected evidence, report, and live-state restoration remain unchanged.

- [x] **Step 2: Run all frontend unit tests**

Run: `cd frontend; npm test -- --run`

Expected: all tests PASS.

- [x] **Step 3: Run TypeScript and production builds**

Run: `cd frontend; npm run build`

Expected: `vue-tsc --noEmit` and `vite build` complete successfully.

- [x] **Step 4: Commit the integration**

Run:

```powershell
git add frontend/src/App.vue
git commit -m "refactor: validate readonly demo before rendering"
```

### Task 4: Verify static behavior and update durable documentation

**Files:**
- Modify: `docs/p5-web-guide.md`
- Modify: `docs/problem-solution-log.md`

- [x] **Step 1: Build the static-only profile**

Run:

```powershell
cd frontend
$env:VITE_DEMO_ONLY='true'
npm run build
Remove-Item Env:VITE_DEMO_ONLY
```

Expected: build succeeds and output contains the fixed demo fixture.

- [x] **Step 2: Perform browser acceptance checks**

Open the local Vite page and verify:

```text
all nine field rows contain values
each field opens a paper-page or source-line evidence panel
history shows two screening and two extraction versions
the diff shows additions plus separate 81.2 and 81.3 results
the report matches the card
Agent replay shows the frozen real trajectory and citations
no /v1 request occurs while loading or navigating readonly content
```

- [x] **Step 3: Update documentation**

In `docs/p5-web-guide.md`, replace the two-field description with the complete nine-field walkthrough and conflict-display behavior. Append a problem-log entry recording that the old fixture had one evidence item and two fields, and include test/build/browser verification.

- [x] **Step 4: Run final checks**

Run:

```powershell
cd G:\ICAN\frontend
npm test -- --run
npm run build
cd G:\ICAN
git diff --check
```

Expected: all frontend tests pass, production build succeeds, and `git diff --check` prints no errors.

- [x] **Step 5: Commit documentation and verification changes**

Run:

```powershell
git add docs/p5-web-guide.md docs/problem-solution-log.md
git commit -m "docs: document complete readonly demo walkthrough"
```
