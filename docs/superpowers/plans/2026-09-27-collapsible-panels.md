# Collapsible Workspace Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independent expand/collapse controls to the seven main ICAN workspace panels while preserving all research state and readonly behavior.

**Architecture:** Keep the seven panel keys and immutable visibility transitions in a small pure TypeScript module. `App.vue` owns the page-level state, a focused `PanelCollapseButton.vue` renders the shared accessible control, and `DemoCenter.vue` receives its expanded state through props and emits a toggle request. Panel bodies use `v-show` so hidden content keeps its Vue state.

**Tech Stack:** Vue 3 Composition API, TypeScript, Lucide Vue icons, CSS, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-09-27-collapsible-panels-design.md`

## Global Constraints

- The seven keys are exactly `demo`, `papers`, `card`, `history`, `comparison`, `reproduction`, and `evidence`.
- Every panel is expanded on first load and after a full page refresh.
- Toggling a panel must not clear or rewrite queries, candidates, cards, version selections, reports, Agent results, or evidence.
- Do not write collapse preferences to browser storage and do not add API requests.
- Internal candidate rows, information fields, history rows, Agent events, and citations remain non-collapsible.
- Public readonly demo and local online mode use the same controls.

## Review Focus

- Rapid repeated clicks must only affect the targeted panel and never produce an invalid key or missing state.
- A collapsed card with a populated form or selected version must show the same values when reopened.
- The evidence panel must keep “关闭证据” and “收起” as separate actions.
- Anchor navigation to a collapsed section must still land on its visible heading without silently changing state.
- Narrow layouts must keep collapse controls reachable without overlapping existing actions.

---

### Task 1: Lock the seven-panel state contract

**Files:**
- Create: `frontend/src/panelCollapse.ts`
- Create: `frontend/src/panelCollapse.test.ts`

**Interfaces:**
- Produces: `panelKeys`, `PanelKey`, `PanelVisibility`, `createPanelVisibility()`, and `togglePanelVisibility(state, key)`.
- Consumes: no Vue runtime; the module remains deterministic and testable in isolation.

- [x] **Step 1: Write the failing state tests**

Create `frontend/src/panelCollapse.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  createPanelVisibility,
  panelKeys,
  togglePanelVisibility,
} from './panelCollapse'

describe('workspace panel visibility', () => {
  it('starts all seven main panels expanded', () => {
    const state = createPanelVisibility()
    expect(panelKeys).toEqual([
      'demo', 'papers', 'card', 'history',
      'comparison', 'reproduction', 'evidence',
    ])
    expect(panelKeys.every(key => state[key])).toBe(true)
  })

  it('toggles only the requested panel and keeps the prior snapshot unchanged', () => {
    const initial = createPanelVisibility()
    const collapsed = togglePanelVisibility(initial, 'card')
    expect(collapsed.card).toBe(false)
    expect(collapsed.history).toBe(true)
    expect(initial.card).toBe(true)
    expect(togglePanelVisibility(collapsed, 'card').card).toBe(true)
  })
})
```

- [x] **Step 2: Run the test and verify it fails**

Run: `cd frontend; npm test -- --run src/panelCollapse.test.ts`

Expected: FAIL because `panelCollapse.ts` does not exist.

- [x] **Step 3: Implement the pure state module**

Create `frontend/src/panelCollapse.ts`:

```ts
export const panelKeys = [
  'demo',
  'papers',
  'card',
  'history',
  'comparison',
  'reproduction',
  'evidence',
] as const

export type PanelKey = typeof panelKeys[number]
export type PanelVisibility = Record<PanelKey, boolean>

export function createPanelVisibility(): PanelVisibility {
  return Object.fromEntries(panelKeys.map(key => [key, true])) as PanelVisibility
}

export function togglePanelVisibility(
  state: PanelVisibility,
  key: PanelKey,
): PanelVisibility {
  return { ...state, [key]: !state[key] }
}
```

- [x] **Step 4: Run the focused test**

Run: `cd frontend; npm test -- --run src/panelCollapse.test.ts`

Expected: 2 tests PASS.

- [x] **Step 5: Commit the state contract**

```powershell
git add frontend/src/panelCollapse.ts frontend/src/panelCollapse.test.ts
git commit -m "test: define workspace panel visibility contract"
```

### Task 2: Build the shared accessible collapse control

**Files:**
- Create: `frontend/src/components/PanelCollapseButton.vue`
- Modify: `frontend/src/style.css`

**Interfaces:**
- Consumes: `expanded: boolean`, `controls: string`, and `label: string` props.
- Produces: a `toggle` event and a button whose visible label, icon, `aria-label`, `aria-expanded`, and `aria-controls` all describe the next action and controlled body.

- [x] **Step 1: Create the shared button component**

Create `frontend/src/components/PanelCollapseButton.vue`:

```vue
<script setup lang="ts">
import { ChevronDown, ChevronUp } from '@lucide/vue'

defineProps<{
  expanded: boolean
  controls: string
  label: string
}>()

defineEmits<{ toggle: [] }>()
</script>

<template>
  <button
    type="button"
    class="text-button panel-collapse-button"
    :aria-label="`${expanded ? '收起' : '展开'}${label}`"
    :aria-expanded="expanded"
    :aria-controls="controls"
    @click="$emit('toggle')"
  >
    <ChevronUp v-if="expanded" :size="17" aria-hidden="true" />
    <ChevronDown v-else :size="17" aria-hidden="true" />
    {{ expanded ? '收起' : '展开' }}
  </button>
</template>
```

- [x] **Step 2: Add shared layout styles**

Append focused rules to `frontend/src/style.css`:

```css
.panel-collapse-button {
  flex: 0 0 auto;
  min-height: 36px;
  white-space: nowrap;
}

.panel-heading-actions,
.evidence-title-actions,
.section-heading-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.section-heading-actions > span {
  color: #899aa5;
  font-size: 12px;
  white-space: nowrap;
}

.demo-center-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
}

.demo-center-summary-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.evidence-close-button {
  background: none;
  border: 0;
  color: #8394a0;
  padding: 3px;
}

.is-collapsed {
  min-height: 0;
}

.reproduction-section .panel-body > p {
  color: #687e8a;
  font-size: 12px;
  line-height: 1.7;
  padding: 0 17px;
}

@media (max-width: 720px) {
  .panel-heading-actions,
  .evidence-title-actions,
  .section-heading-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .section-heading-actions > span {
    display: none;
  }

  .demo-center-summary {
    align-items: flex-start;
    padding: 18px 15px;
    flex-direction: column;
  }
}
```

Replace the broad existing `.evidence-title button` rule with `.evidence-close-button`, and add that class to the existing close button, so the collapse control keeps `text-button` styling. Keep the existing `.reproduction-section > p` selector during migration and add the `.panel-body > p` form above so the wrapped explanatory copy retains its typography. Do not add transitions that delay content visibility or leave focusable hidden descendants during animation.

- [x] **Step 3: Run TypeScript and production build**

Run: `cd frontend; npm run build`

Expected: Vue TypeScript checking and Vite production build PASS.

- [x] **Step 4: Commit the shared control**

```powershell
git add frontend/src/components/PanelCollapseButton.vue frontend/src/style.css
git commit -m "feat: add accessible panel collapse control"
```

### Task 3: Connect all seven main panels

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/DemoCenter.vue`
- Test: `frontend/src/panelCollapse.test.ts`

**Interfaces:**
- Consumes: `createPanelVisibility()` and `togglePanelVisibility()` from Task 1; `PanelCollapseButton` from Task 2.
- Produces: independent controls for all seven panel keys, with body IDs `demo-panel-body`, `papers-panel-body`, `card-panel-body`, `history-panel-body`, `comparison-panel-body`, `reproduction-panel-body`, and `evidence-panel-body`.

- [x] **Step 1: Add page-level visibility state**

In `frontend/src/App.vue`, import the shared component and state helpers:

```ts
import PanelCollapseButton from './components/PanelCollapseButton.vue'
import {
  createPanelVisibility,
  togglePanelVisibility,
  type PanelKey,
} from './panelCollapse'

const panelVisibility = ref(createPanelVisibility())

function togglePanel(key: PanelKey) {
  panelVisibility.value = togglePanelVisibility(panelVisibility.value, key)
}
```

Do not add this state to `savedLiveState`; entering or leaving the readonly demo must not reset the user's current layout.

- [x] **Step 2: Connect DemoCenter through props and events**

Change the call in `App.vue` to:

```vue
<DemoCenter
  :demo-mode="demoMode"
  :busy="busy !== null"
  :static-demo-only="staticDemoOnly"
  :expanded="panelVisibility.demo"
  @load-demo="loadDemoCase"
  @toggle-collapse="togglePanel('demo')"
/>
```

In `frontend/src/components/DemoCenter.vue`, add `expanded?: boolean` with a default of `true`, add `toggle-collapse` to `defineEmits`, and import `PanelCollapseButton`. Create a persistent `.demo-center-summary` containing the current eyebrow and title on the left, plus the current `demo-mode-value` status and collapse control in `.demo-center-summary-actions` on the right. Immediately after that row, open `<div id="demo-panel-body" v-show="expanded" class="panel-body">`; move the current descriptive paragraph, mode explanation and actions, `.demo-stage-nav`, and `.demo-center-foot` inside it, then close the body before the outer section closes. The current mode value appears only in the summary row. Do not alter business text, event handlers, disabled states, links, loop expressions, or readonly conditions.

The header button must be:

```vue
<PanelCollapseButton
  :expanded="expanded"
  controls="demo-panel-body"
  label="演示中心"
  @toggle="emit('toggle-collapse')"
/>
```

- [x] **Step 3: Wrap the five content-column panel bodies**

For `papers`, `card`, `history`, `comparison`, and `reproduction` in `App.vue`:

1. Keep the existing numbered heading visible.
2. Put existing business buttons and `PanelCollapseButton` in a heading action wrapper.
3. Add `:class="{ 'is-collapsed': !panelVisibility.<key> }"` to the outer section.
4. Wrap everything after the heading in `<div id="<key>-panel-body" v-show="panelVisibility.<key>" class="panel-body">`.
5. Bind each collapse button to its matching key, body ID, and Chinese panel label.

For example, the card heading action ends with:

```vue
<PanelCollapseButton
  :expanded="panelVisibility.card"
  controls="card-panel-body"
  label="实验信息卡"
  @toggle="togglePanel('card')"
/>
```

Preserve every existing `v-if`, submit handler, disabled state, and readonly guard inside the body.

- [x] **Step 4: Connect the evidence panel without changing close behavior**

Keep the evidence title visible. Put the existing close button and this new control in `.evidence-title-actions`:

```vue
<PanelCollapseButton
  :expanded="panelVisibility.evidence"
  controls="evidence-panel-body"
  label="原文证据"
  @toggle="togglePanel('evidence')"
/>
```

Wrap only the evidence metadata, excerpt, source link, and footer note in `#evidence-panel-body`. The existing close button must continue to set `proof = null` and must not change `panelVisibility.evidence`.

- [x] **Step 5: Run focused and full frontend tests**

Run:

```powershell
cd frontend
npm test -- --run src/panelCollapse.test.ts
npm test -- --run
```

Expected: focused state tests and all frontend tests PASS.

- [x] **Step 6: Run default and readonly builds**

Run:

```powershell
cd frontend
npm run build
$env:VITE_DEMO_ONLY='true'
try { npm run build } finally { Remove-Item Env:VITE_DEMO_ONLY -ErrorAction SilentlyContinue }
```

Expected: both production profiles PASS.

- [x] **Step 7: Commit the seven-panel integration**

Because `App.vue` already contains unrelated uncommitted work, stage only the collapse-state imports, state function, and template hunks for this feature. Then commit:

```powershell
git add frontend/src/components/DemoCenter.vue
git add -p frontend/src/App.vue
git commit -m "feat: make workspace panels collapsible"
```

### Task 4: Browser acceptance and durable documentation

**Files:**
- Modify: `docs/p5-web-guide.md`
- Modify: `docs/problem-solution-log.md`

**Interfaces:**
- Consumes: the completed seven-panel UI from Task 3.
- Produces: verified desktop and narrow-screen behavior plus user-facing instructions.

- [x] **Step 1: Verify all seven controls in the running browser**

At `http://127.0.0.1:5173/`, load the Swin readonly replay and check:

```text
演示中心、论文筛选、实验信息卡、历史版本、对照报告、复现核查、原文证据均有按钮
每张卡片可独立收起和重新展开
按钮文字、箭头和 aria-expanded 同步
收起后标题仍可见
信息卡、历史版本、Agent 回放和证据在重新展开后内容不丢失
“关闭证据”只清空当前证据，“收起”只隐藏正文
侧边导航能定位到已收起卡片的可见标题，且不会擅自改变展开状态
```

- [x] **Step 2: Verify readonly network isolation**

Inspect browser resource timing after loading and toggling panels. Expected: no resource URL contains `/v1`.

- [x] **Step 3: Verify narrow layout**

Use a viewport no wider than 720 CSS pixels. Confirm heading actions wrap below the title, every toggle remains visible, and no horizontal page overflow is introduced. Reset the temporary viewport afterward.

- [x] **Step 4: Update documentation**

Add a short “展开与收起” subsection to `docs/p5-web-guide.md` stating that all seven main cards default to expanded, retain state while hidden, and reset layout after refresh. Append a problem-log entry describing the long-page usability issue, implementation boundary, and browser/build verification.

- [x] **Step 5: Run final checks**

Run:

```powershell
cd G:\ICAN\frontend
npm test -- --run
npm run build
cd G:\ICAN
git diff --check
```

Expected: all frontend tests PASS, production build PASS, and `git diff --check` prints no errors.

- [x] **Step 6: Commit documentation and verification results**

Stage `docs/p5-web-guide.md` and only the new collapse entry from `docs/problem-solution-log.md`, preserving the unrelated existing entry, then commit:

```powershell
git commit -m "docs: document collapsible workspace panels"
```
