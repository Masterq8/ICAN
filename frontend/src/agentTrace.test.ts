import { describe, expect, it } from 'vitest'
import { displayTrajectory, eventStatusLabel, agentStatusLabel, citedEvidence } from './agentTrace'
import type { AgentResponse, AgentTrajectoryEvent, Evidence } from './types'

const evidence: Evidence = {
  rank: 1,
  score: 0.9,
  chunk_id: 'chunk-1',
  text: 'A source sentence.',
  review_required: false,
  source: {
    source_id: 'paper-1',
    source_type: 'paper',
    source_path: 'paper.pdf',
    source_version: 'arXiv:v2',
    location: { page: 3 },
  },
}

describe('displayTrajectory', () => {
  it('keeps real event order and labels planner, tool and status states', () => {
    const events: AgentTrajectoryEvent[] = [
      { event: 'planning', turn: 1, parameter_summary: '', status: 'planned', result_summary: '第 1 轮工具规划已返回', cached: false },
      { event: 'tool', turn: 1, tool: 'search_evidence', parameter_summary: '查询 “LayerNorm”', status: 'completed', result_summary: '检索到 2 项证据', cached: false },
      { event: 'tool', turn: 2, tool: 'read_evidence', parameter_summary: '', status: 'cached', result_summary: '读取到 1 项证据', cached: true },
      { event: 'tool', turn: 3, tool: 'unknown_tool', parameter_summary: '', status: 'failed', result_summary: '工具未能完成', cached: false },
    ]

    expect(displayTrajectory(events).map(item => [item.title, item.statusLabel])).toEqual([
      ['第 1 轮工具规划', '已返回工具选择'],
      ['检索语料', '已完成'],
      ['读取证据', '命中缓存'],
      ['未知工具', '失败'],
    ])
  })

  it('bounds all displayed summaries and preserves unknown backend states', () => {
    const event: AgentTrajectoryEvent = {
      event: 'tool', turn: 1, tool: 'future_tool', parameter_summary: 'p'.repeat(400),
      status: 'future_status' as AgentTrajectoryEvent['status'], result_summary: 'r'.repeat(400), cached: false,
    }
    const [display] = displayTrajectory([event])

    expect(display.title).toBe('未知工具')
    expect(display.statusLabel).toBe('其他状态：future_status')
    expect(display.parameterSummary).toHaveLength(240)
    expect(display.resultSummary).toHaveLength(240)
  })

  it('returns an empty list for a missing trace', () => {
    expect(displayTrajectory([])).toEqual([])
  })
})

describe('Agent response labels and citations', () => {
  it('does not interpret unknown task status as success', () => {
    expect(agentStatusLabel('future_status')).toBe('其他状态：future_status')
    expect(eventStatusLabel('failed')).toBe('失败')
  })

  it('extracts only source evidence from the returned citations', () => {
    const response = {
      answer: { answer: 'A grounded answer.', status: 'answered', citations: [{ number: 1, context_id: 'ctx-1', evidence }] },
    } as AgentResponse

    expect(citedEvidence(response)).toEqual([evidence])
    expect(citedEvidence({ ...response, answer: null })).toEqual([])
  })
})
