import type { AgentResponse, Candidate, CardResponse, Collection, ComparisonResponse, Evidence, ResearchHistory, ResearchRecord } from './types'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function post<T>(path: string, body: object): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('无法连接服务，请检查后端是否启动。')
  }
  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? String((payload as { detail: unknown }).detail)
      : `请求失败（${response.status}）`
    throw new ApiError(detail, response.status)
  }
  return payload as T
}

export function discover(query: string, collection: Collection): Promise<{ candidates: Candidate[] }> {
  return post('/v1/research/discover', { query, collection, limit: 4 })
}

export function generateCard(query: string, collection: Collection, source_id: string): Promise<CardResponse> {
  return post('/v1/research/auto-card', { query, collection, source_id })
}

export function loadCard(query: string, collection: Collection, source_id: string): Promise<CardResponse> {
  return post('/v1/research/load-card', { query, collection, source_id })
}

export function compareCards(record_ids: string[]): Promise<ComparisonResponse> {
  return post('/v1/research/compare', { record_ids })
}

export function getResearchHistory(source_id: string): Promise<ResearchHistory> {
  return get(`/v1/research/history/${encodeURIComponent(source_id)}`)
}

async function get<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(path)
  } catch {
    throw new Error('无法连接服务，请检查后端是否启动。')
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? String((payload as { detail: unknown }).detail)
      : `请求失败（${response.status}）`
    throw new ApiError(detail, response.status)
  }
  return payload as T
}

export function searchPaperEvidence(query: string, collection: Collection, source_id: string): Promise<{ results: Evidence[] }> {
  return post('/v1/research/evidence-search', { query, collection, source_id, limit: 6 })
}


function paperScope(query: string, candidate: Candidate) {
  return {
    query,
    collection: candidate.collection,
    family: candidate.collection === 'swin_v1' ? 'swin_v1' : 'auto',
    filters: { source_types: ['paper'], path_prefixes: [candidate.source_path] },
  }
}

export function reviseScreening(query: string, candidate: Candidate, revision_of: string, decision: 'include' | 'exclude' | 'hold', reason: string, evidence_id: string): Promise<ResearchRecord> {
  return post('/v1/research/screening', {
    scope: paperScope(query, candidate),
    draft: {
      subject_source_id: candidate.source_id,
      decision,
      revision_of,
      claims: [{ statement: reason, kind: 'inference', evidence_ids: [evidence_id] }],
    },
  })
}

export function reviseExtraction(query: string, candidate: Candidate, revision_of: string | null, fields: Array<{ name: string; value: string; claims: ResearchRecord["claims"][number]["claim"][] }>): Promise<ResearchRecord> {
  return post('/v1/research/extraction', {
    scope: paperScope(query, candidate),
    draft: {
      subject_source_id: candidate.source_id,
      revision_of,
      fields: fields.map(field => ({ name: field.name, value: field.value, claims: field.claims })),
    },
  })
}

export function runAgent(query: string, required_claim_kinds: string[]): Promise<AgentResponse> {
  return post('/v1/agent/run', {
    query,
    collection: 'swin_v1',
    family: 'swin_v1',
    required_claim_kinds,
  })
}
