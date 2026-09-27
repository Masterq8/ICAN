import type {
  Candidate,
  ClaimVerdict,
  ResearchHistory,
  ResearchRecord,
} from './types'

export const requiredDemoFields = [
  'task',
  'model',
  'dataset',
  'input_setting',
  'training',
  'metric',
  'result',
  'limitation',
  'code_availability',
] as const

export interface DemoFixture {
  label: string
  query: string
  candidate: Candidate
  history: ResearchHistory
  report: string
}

function hydrateRecord(
  record: ResearchRecord,
  candidate: Candidate,
): ResearchRecord {
  const evidenceById = new Map(
    candidate.evidence.map(item => [item.chunk_id, item]),
  )
  const attachEvidence = (verdict: ClaimVerdict): ClaimVerdict => {
    const evidence = verdict.claim.evidence_ids.map(id => evidenceById.get(id))
    if (evidence.some(item => item === undefined)) {
      throw new Error('Readonly demo references missing evidence')
    }
    const resolvedEvidence = evidence.filter(item => item !== undefined)
    if (
      verdict.claim.quote &&
      !resolvedEvidence.some(item => item.text.includes(verdict.claim.quote))
    ) {
      throw new Error('Readonly demo quote is not present in evidence')
    }
    return { ...verdict, evidence: resolvedEvidence }
  }

  return {
    ...record,
    claims: record.claims.map(attachEvidence),
    fields: record.fields.map(field => ({
      ...field,
      claims: field.claims.map(attachEvidence),
    })),
  }
}

export function hydrateAndValidateDemoFixture(raw: unknown): DemoFixture {
  const fixture = raw as DemoFixture
  if (!fixture.label?.includes('预置演示数据')) {
    throw new Error('Readonly demo label is missing')
  }
  if (
    fixture.history?.screening?.length < 2 ||
    fixture.history?.extraction?.length < 2
  ) {
    throw new Error('Readonly demo requires two history versions')
  }

  const latestExtraction = fixture.history.extraction[0]
  const fieldNames = new Set(latestExtraction.fields.map(field => field.name))
  if (requiredDemoFields.some(name => !fieldNames.has(name))) {
    throw new Error('Readonly demo card is incomplete')
  }
  if (
    fixture.history.screening[0].revision_of !==
      fixture.history.screening[1].record_id ||
    latestExtraction.revision_of !== fixture.history.extraction[1].record_id
  ) {
    throw new Error('Readonly demo revision chain is invalid')
  }

  return {
    ...fixture,
    history: {
      screening: fixture.history.screening.map(record =>
        hydrateRecord(record, fixture.candidate),
      ),
      extraction: fixture.history.extraction.map(record =>
        hydrateRecord(record, fixture.candidate),
      ),
      diagnostics: [],
    },
  }
}
