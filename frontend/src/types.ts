export type Collection = 'swin_v1' | 'qasper_train_v1' | 'vision_mamba_v1'
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
  created_at: string
  card_id?: string | null
  revision_of?: string | null
  record_type: 'screening' | 'extraction'
  subject_source_id: string
  decision?: 'include' | 'exclude' | 'hold'
  claims: ClaimVerdict[]
  fields: Array<{ name: string; value: string; claims: ClaimVerdict[]; semantic_diagnostics?: unknown[] }>
}

export interface ResearchHistory {
  screening: ResearchRecord[]
  extraction: ResearchRecord[]
  diagnostics: Array<{ record_id: string; code: 'invalid_json' | 'invalid_record' | 'unreadable' }>
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
  stages: Array<{ stage: 'evidence_preparation' | 'model_submission' | 'result_validation' | 'record_save'; status: 'completed' | 'failed' | 'skipped' }>
  stop_reason: 'completed' | 'tool_submission_rejected' | 'model_request_failed' | 'model_unavailable' | 'model_timeout' | 'budget_exhausted' | 'record_save_failed'
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

export interface AgentTrajectoryEvent {
  event: 'planning' | 'tool'
  turn: number
  tool?: string | null
  parameter_summary: string
  status: 'planned' | 'completed' | 'cached' | 'failed' | null
  result_summary: string
  cached: boolean
}

export interface AgentCitation {
  number: number
  context_id: string
  evidence: Evidence
}

export interface AgentResponse {
  task_id: string
  status: string
  stop_reason: string
  answer: { answer: string; status: string; citations: AgentCitation[] } | null
  artifacts: Array<{ kind: string; verdicts?: ClaimVerdict[] }>
  trajectory: AgentTrajectoryEvent[]
  workflow_mode: 'tool_loop' | 'verified'
  workflow_stages: Array<{ stage: string; status: string }>
  usage: {
    paid_calls: number
    planner_calls: number
    answer_calls: number
    prompt_tokens: number
    completion_tokens: number
    usage_missing_calls: number
    actual_cost_usd: number | null
  }
  index_fingerprint: string | null
  paperqa_version: string
  planner_model: string
  answer_model: string
}
