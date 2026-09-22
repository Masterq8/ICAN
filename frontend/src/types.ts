export type Collection = 'swin_v1' | 'qasper_train_v1'
export type ClaimStatus = 'supported' | 'requires_review' | 'insufficient_evidence' | 'blocked_by_precondition'

export interface Evidence {
  rank: number
  score: number
  chunk_id: string
  text: string
  review_required: boolean
  source: {
    source_id: string
    source_type: string
    source_path: string
    source_version: string
    location: Record<string, string | number>
  }
}

export interface Candidate {
  collection: Collection
  source_id: string
  title: string
  source_path: string
  source_version: string
  evidence: Evidence[]
}

export interface ClaimVerdict {
  status: ClaimStatus
  claim: { statement: string; kind: string; evidence_ids: string[]; quote?: string | null }
  evidence: Evidence[]
  diagnostics: string[]
}

export interface ResearchRecord {
  record_id: string
  revision_of?: string | null
  record_type: 'screening' | 'extraction'
  subject_source_id: string
  decision?: 'include' | 'exclude' | 'hold'
  claims: ClaimVerdict[]
  fields: Array<{ name: string; value: string; claims: ClaimVerdict[] }>
}

export interface CardResponse {
  candidate: Candidate
  screening: ResearchRecord
  extraction: ResearchRecord | null
  usage: { paid_calls: number; prompt_tokens: number; completion_tokens: number; actual_cost_usd: null }
}

export interface ComparisonResponse {
  record_ids: string[]
  comparable: boolean
  warnings: string[]
  markdown: string
}

export interface AgentResponse {
  status: string
  stop_reason: string
  answer: { answer: string; status: string; citations: Evidence[] } | null
  artifacts: Array<{ kind: string; verdicts?: ClaimVerdict[] }>
  workflow_stages: Array<{ stage: string; status: string }>
  usage: { paid_calls: number; prompt_tokens: number; completion_tokens: number; actual_cost_usd: null }
}
