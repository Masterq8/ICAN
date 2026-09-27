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
