import type { ClaimVerdict, ResearchHistory, ResearchRecord } from './types'

export type ChangeKind = 'added' | 'removed' | 'modified' | 'unchanged'

export interface VersionDiffRow {
  key: string
  label: string
  change: ChangeKind
  before: { value: string; claims: ClaimVerdict[] } | null
  after: { value: string; claims: ClaimVerdict[] } | null
  needsReview: boolean
}

export function historyForSubjectAndType(
  history: ResearchHistory,
  subjectSourceId: string,
  recordType: 'screening' | 'extraction',
): ResearchRecord[] {
  return history[recordType]
    .filter(record => record.subject_source_id === subjectSourceId && record.record_type === recordType)
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at) || right.record_id.localeCompare(left.record_id))
}

export function selectLatestPair(records: ResearchRecord[]): [ResearchRecord | null, ResearchRecord | null] {
  const sorted = records.slice().sort((left, right) => right.created_at.localeCompare(left.created_at) || right.record_id.localeCompare(left.record_id))
  return [sorted[1] ?? null, sorted[0] ?? null]
}

function normalize(value: string): string {
  return value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase()
}

function claimsEqual(left: ClaimVerdict[], right: ClaimVerdict[]): boolean {
  return JSON.stringify(left.map(item => ({
    statement: item.claim.statement,
    status: item.status,
    quote: item.claim.quote ?? null,
    evidence: item.evidence.map(e => [e.chunk_id, e.source.location]),
  }))) === JSON.stringify(right.map(item => ({
    statement: item.claim.statement,
    status: item.status,
    quote: item.claim.quote ?? null,
    evidence: item.evidence.map(e => [e.chunk_id, e.source.location]),
  })))
}

function fieldValue(field: ResearchRecord['fields'][number]) {
  return { value: field.value, claims: field.claims }
}

export function compareRecords(left: ResearchRecord, right: ResearchRecord): VersionDiffRow[] {
  if (left.subject_source_id !== right.subject_source_id || left.record_type !== right.record_type) {
    throw new Error('只能比较同一论文、同一类型的研究记录。')
  }
  if (left.record_type === 'screening') {
    const rows: VersionDiffRow[] = []
    const decisionLeft = left.decision ?? ''
    const decisionRight = right.decision ?? ''
    rows.push({
      key: 'decision', label: '筛选决定', change: decisionLeft === decisionRight ? 'unchanged' : 'modified',
      before: { value: decisionLeft, claims: [] }, after: { value: decisionRight, claims: [] }, needsReview: false,
    })
    const count = Math.max(left.claims.length, right.claims.length)
    for (let index = 0; index < count; index += 1) {
      const before = left.claims[index]
      const after = right.claims[index]
      rows.push({
        key: `reason-${index}`, label: `理由 ${index + 1}`,
        change: !before ? 'added' : !after ? 'removed' : before.claim.statement === after.claim.statement && claimsEqual([before], [after]) ? 'unchanged' : 'modified',
        before: before ? { value: before.claim.statement, claims: [before] } : null,
        after: after ? { value: after.claim.statement, claims: [after] } : null,
        needsReview: false,
      })
    }
    return rows
  }

  const before = left.fields
  const after = right.fields
  const rightUsed = new Set<number>()
  const pairForLeft = new Map<number, number>()
  const leftUsed = new Set<number>()
  const ambiguousLeft = new Set<number>()
  const ambiguousRight = new Set<number>()
  const names = [...new Set([...before.map(field => normalize(field.name)), ...after.map(field => normalize(field.name))])]
  for (const name of names) {
    const leftIndexes = before.map((field, index) => normalize(field.name) === name ? index : -1).filter(index => index >= 0)
    const rightIndexes = after.map((field, index) => normalize(field.name) === name ? index : -1).filter(index => index >= 0)
    if (leftIndexes.length > 1 || rightIndexes.length > 1) {
      leftIndexes.forEach(index => ambiguousLeft.add(index))
      rightIndexes.forEach(index => ambiguousRight.add(index))
    }
    for (const leftIndex of leftIndexes) {
      const match = rightIndexes.find(index => !rightUsed.has(index) && normalize(after[index].value) === normalize(before[leftIndex].value))
      if (match !== undefined) {
        pairForLeft.set(leftIndex, match)
        leftUsed.add(leftIndex)
        rightUsed.add(match)
      }
    }
    const remainingLeft = leftIndexes.filter(index => !leftUsed.has(index))
    const remainingRight = rightIndexes.filter(index => !rightUsed.has(index))
    while (remainingLeft.length && remainingRight.length) {
      const leftIndex = remainingLeft.shift()!
      const rightIndex = remainingRight.shift()!
      pairForLeft.set(leftIndex, rightIndex)
      leftUsed.add(leftIndex)
      rightUsed.add(rightIndex)
    }
  }

  const rows = before.map((field, index): VersionDiffRow => {
    const rightIndex = pairForLeft.get(index)
    const next = rightIndex === undefined ? null : after[rightIndex]
    const ambiguous = ambiguousLeft.has(index)
    return {
      key: `before-${index}`,
      label: `${field.name} · ${before.slice(0, index + 1).filter(item => item.name === field.name).length}`,
      change: !next ? 'removed' : normalize(field.value) === normalize(next.value) && claimsEqual(field.claims, next.claims) ? 'unchanged' : 'modified',
      before: fieldValue(field),
      after: next ? fieldValue(next) : null,
      needsReview: ambiguous,
    }
  })
  after.forEach((field, index) => {
    if (!rightUsed.has(index)) rows.push({
      key: `after-${index}`, label: `${field.name} · 新增`, change: 'added', before: null, after: fieldValue(field),
      needsReview: ambiguousRight.has(index),
    })
  })
  return rows
}
