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
  status: 'completed' | 'review_required'
  candidate: Candidate
  screening: ResearchRecord | null
  extraction: ResearchRecord | null
  usage: { paid_calls: number; prompt_tokens: number; completion_tokens: number; actual_cost_usd: null }
  high_confidence_fields: HighConfidenceField[]
  review_candidates: ReviewCandidate[]
  failure_code?: string | null
}

export interface HighConfidenceField {
  occurrence: number
  source_id: string
  name: string
  value: string
  quote: string
  evidence_id: string
  confidence_reasons: string[]
}

export interface ReviewCandidate {
  occurrence: number
  source_id: string
  name: string
  value: string
  quote: string
  evidence_id: string
  reason_codes: string[]
  reason: string
  allowed_actions: Array<'open_evidence' | 'search_same_paper' | 'edit_and_save' | 'ignore'>
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
