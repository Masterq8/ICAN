import { describe, expect, it } from 'vitest'
import { compareRecords, historyForSubjectAndType, selectLatestPair } from './versionDiff'
import type { ResearchHistory, ResearchRecord } from './types'

function record(type: 'screening' | 'extraction', data: Partial<ResearchRecord> = {}): ResearchRecord {
  return {
    record_id: 'r1', created_at: '2026-09-23T00:00:00Z', record_type: type,
    subject_source_id: 'paper-a', decision: type === 'screening' ? 'include' : undefined,
    claims: [], fields: [], ...data,
  }
}

const field = (name: string, value: string) => ({ name, value, claims: [] })

describe('compareRecords', () => {
  it('classifies unchanged, modified, added and removed fields while preserving input order', () => {
    const rows = compareRecords(
      record('extraction', { fields: [field('model', 'Swin-T'), field('dataset', 'ImageNet-1K'), field('result', '81%')] }),
      record('extraction', { fields: [field('result', '82%'), field('model', 'Swin-T'), field('metric', 'Top-1 accuracy')] }),
    )
    expect(rows.map(row => [row.label.split(' · ')[0], row.change])).toEqual([
      ['model', 'unchanged'], ['dataset', 'removed'], ['result', 'modified'], ['metric', 'added'],
    ])
  })

  it('pairs repeated same-name entries by exact value before order and flags ambiguity', () => {
    const rows = compareRecords(
      record('extraction', { fields: [field('result', 'A'), field('result', 'B')] }),
      record('extraction', { fields: [field('result', 'B'), field('result', 'C')] }),
    )
    expect(rows.map(row => [row.before?.value, row.after?.value, row.change])).toEqual([
      ['A', 'C', 'modified'], ['B', 'B', 'unchanged'],
    ])
    expect(rows.map(row => row.needsReview)).toEqual([true, true])
  })

  it('compares screening decision and reason claims', () => {
    const rows = compareRecords(record('screening', { decision: 'include' }), record('screening', { decision: 'hold' }))
    expect(rows[0].change).toBe('modified')
  })

  it('rejects cross-paper and cross-type comparisons', () => {
    expect(() => compareRecords(record('extraction'), record('extraction', { subject_source_id: 'paper-b' }))).toThrow('同一论文')
    expect(() => compareRecords(record('screening'), record('extraction'))).toThrow('同一论文')
  })

  it('defaults to the latest two same-subject versions of one type only', () => {
    const old = record('extraction', { record_id: '00000000-0000-4000-8000-000000000001', created_at: '2026-09-20T00:00:00Z' })
    const latest = record('extraction', { record_id: '00000000-0000-4000-8000-000000000002', created_at: '2026-09-22T00:00:00Z' })
    const unrelated = record('extraction', { record_id: '00000000-0000-4000-8000-000000000003', subject_source_id: 'paper-b' })
    const otherType = record('screening', { record_id: '00000000-0000-4000-8000-000000000004' })
    const history: ResearchHistory = {
      screening: [otherType], extraction: [old, unrelated, latest], diagnostics: [],
    }
    const scoped = historyForSubjectAndType(history, 'paper-a', 'extraction')
    expect(scoped.map(item => item.record_id)).toEqual([latest.record_id, old.record_id])
    expect(selectLatestPair(scoped).map(item => item?.record_id)).toEqual([old.record_id, latest.record_id])
  })
})
