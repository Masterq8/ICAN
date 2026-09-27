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
  return Object.fromEntries(
    panelKeys.map(key => [key, true]),
  ) as PanelVisibility
}

export function togglePanelVisibility(
  state: PanelVisibility,
  key: PanelKey,
): PanelVisibility {
  return { ...state, [key]: !state[key] }
}
