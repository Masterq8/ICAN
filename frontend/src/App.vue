<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import {
  AlertCircle,
  ArrowDownToLine,
  BookOpenText,
  Check,
  CheckCheck,
  ClipboardList,
  ExternalLink,
  FileSearch,
  FileText,
  FolderOpen,
  GitCompareArrows,
  LoaderCircle,
  PencilLine,
  Search,
  Save,
  ShieldCheck,
  X,
} from '@lucide/vue'
import { ApiError, compareCards, discover, generateCard, getResearchHistory, loadCard, reviseExtraction, reviseScreening, runAgent, searchPaperEvidence } from './api'
import type { AgentResponse, Candidate, CardResponse, ClaimStatus, Collection, ComparisonResponse, Evidence, ResearchHistory, ResearchRecord, ReviewCandidate } from './types'
import demoFixture from './demo/swin-case.json'
import { compareRecords, historyForSubjectAndType, selectLatestPair } from './versionDiff'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
const collection = ref<Collection>('swin_v1')
const query = ref('视觉模型如何处理不同输入分辨率？')
const candidates = ref<Candidate[]>([])
const selected = ref<string[]>([])
const activeId = ref<string | null>(null)
const cards = ref<Record<string, CardResponse>>({})
const report = ref<ComparisonResponse | null>(null)
const proof = ref<Evidence | null>(null)
const agentQuery = ref('')
const agentClaimKind = ref('code_execution')
const agentResult = ref<AgentResponse | null>(null)
const busy = ref<'search' | 'card' | 'load' | 'compare' | 'agent' | 'screening' | 'extraction' | 'evidence' | null>(null)
const error = ref('')
const serviceOnline = ref<boolean | null>(null)
const searchCompleted = ref(false)
const demoMode = ref(false)
const demoReport = ref('')
const researchHistory = ref<ResearchHistory | null>(null)
const historyError = ref('')
const historyBusy = ref(false)
const historyType = ref<'screening' | 'extraction'>('extraction')
const historyLeftId = ref('')
const historyRightId = ref('')
const editingScreening = ref(false)
const editingExtraction = ref(false)
const screeningDecision = ref<'include' | 'exclude' | 'hold'>('hold')
const screeningReason = ref('')
const editFields = ref<Array<{ name: string; value: string; originalIndex: number }>>([])
const reviewSearch = ref('')
const reviewEvidence = ref<Evidence[]>([])
const reviewEdits = ref<Record<number, { name: string; value: string; quote: string; evidence_id: string }>>({})

const fields = [
  ['task', '任务'], ['model', '模型'], ['dataset', '数据集'], ['input_setting', '输入设置'],
  ['training', '训练'], ['metric', '指标'], ['result', '结果'], ['limitation', '限制'],
  ['code_availability', '代码入口'],
] as const

const active = computed(() => candidates.value.find(item => item.source_id === activeId.value) ?? null)
const activeCard = computed(() => activeId.value ? cards.value[activeId.value] : null)
const comparisonIds = computed(() => selected.value
  .map(id => cards.value[id]?.extraction?.record_id)
  .filter((id): id is string => Boolean(id)))
const reportHtml = computed(() => report.value ? DOMPurify.sanitize(markdown.render(report.value.markdown)) : '')
const historyRecords = computed(() => active.value && researchHistory.value
  ? historyForSubjectAndType(researchHistory.value, active.value.source_id, historyType.value)
  : [])
const selectedHistoryLeft = computed(() => historyRecords.value.find(record => record.record_id === historyLeftId.value) ?? null)
const selectedHistoryRight = computed(() => historyRecords.value.find(record => record.record_id === historyRightId.value) ?? null)
const historyDiff = computed(() => selectedHistoryLeft.value && selectedHistoryRight.value && historyLeftId.value !== historyRightId.value
  ? compareRecords(selectedHistoryLeft.value, selectedHistoryRight.value)
  : [])

let savedLiveState: null | {
  query: string; collection: Collection; candidates: Candidate[]; selected: string[]; activeId: string | null;
  searchCompleted: boolean;
  cards: Record<string, CardResponse>; report: ComparisonResponse | null; proof: Evidence | null;
  editingScreening: boolean; editingExtraction: boolean; screeningDecision: 'include' | 'exclude' | 'hold'; screeningReason: string;
  editFields: typeof editFields.value; reviewSearch: string; reviewEvidence: Evidence[];
  reviewEdits: typeof reviewEdits.value; agentQuery: string; agentClaimKind: string;
  researchHistory: ResearchHistory | null; historyError: string;
  historyType: 'screening' | 'extraction'; historyLeftId: string; historyRightId: string;
  error: string; serviceOnline: boolean | null; agentResult: AgentResponse | null;
} = null
let restoringSnapshot = false
let historyRequestId = 0

watch(collection, next => {
  if (demoMode.value || restoringSnapshot) return
  searchCompleted.value = false
  query.value = next === 'swin_v1'
    ? '视觉模型如何处理不同输入分辨率？'
    : next === 'vision_mamba_v1'
      ? 'Vision Mamba selective scan bidirectional sequence design'
      : 'question answering model evaluation dataset and result'
  candidates.value = []
  selected.value = []
  activeId.value = null
  proof.value = null
  report.value = null
  cards.value = {}
  editingScreening.value = false
  editingExtraction.value = false
  error.value = ''
})

watch(activeId, () => {
  if (demoMode.value || restoringSnapshot) return
  historyRequestId += 1
  editingScreening.value = false
  editingExtraction.value = false
  reviewSearch.value = ''
  reviewEvidence.value = []
  reviewEdits.value = {}
  researchHistory.value = null
  historyError.value = ''
  historyLeftId.value = ''
  historyRightId.value = ''
})

watch(activeId, async sourceId => {
  const paper = candidates.value.find(item => item.source_id === sourceId)
  if (!paper || demoMode.value) return
  const requestId = ++historyRequestId
  historyBusy.value = true
  historyError.value = ''
  try {
    const loadedHistory = await getResearchHistory(paper.source_id)
    if (requestId !== historyRequestId || demoMode.value || activeId.value !== sourceId) return
    researchHistory.value = loadedHistory
    serviceOnline.value = true
    historyType.value = researchHistory.value.extraction.length ? 'extraction' : 'screening'
    const [oldVersion, newVersion] = selectLatestPair(
      historyForSubjectAndType(researchHistory.value, paper.source_id, historyType.value),
    )
    historyLeftId.value = oldVersion?.record_id ?? ''
    historyRightId.value = newVersion?.record_id ?? ''
  } catch (cause) {
    if (requestId !== historyRequestId || demoMode.value || activeId.value !== sourceId) return
    markApiFailure(cause)
    historyError.value = cause instanceof Error ? cause.message : '读取历史记录失败。'
  } finally {
    if (requestId === historyRequestId) historyBusy.value = false
  }
})

function loadDemoCase() {
  if (busy.value !== null) return
  historyRequestId += 1
  historyBusy.value = false
  if (!savedLiveState) savedLiveState = {
    query: query.value, collection: collection.value, candidates: candidates.value, selected: selected.value,
    searchCompleted: searchCompleted.value,
    activeId: activeId.value, cards: cards.value, report: report.value, proof: proof.value,
    editingScreening: editingScreening.value, editingExtraction: editingExtraction.value,
    screeningDecision: screeningDecision.value, screeningReason: screeningReason.value,
    editFields: editFields.value, reviewSearch: reviewSearch.value, reviewEvidence: reviewEvidence.value,
    reviewEdits: reviewEdits.value, agentQuery: agentQuery.value, agentClaimKind: agentClaimKind.value,
    researchHistory: researchHistory.value, historyError: historyError.value,
    historyType: historyType.value, historyLeftId: historyLeftId.value,
    historyRightId: historyRightId.value, error: error.value,
    serviceOnline: serviceOnline.value, agentResult: agentResult.value,
  }
  const fixture = demoFixture as unknown as {
    label: string; query: string; candidate: Candidate; history: ResearchHistory; report: string
  }
  demoMode.value = true
  editingScreening.value = false
  editingExtraction.value = false
  reviewSearch.value = ''
  reviewEvidence.value = []
  reviewEdits.value = {}
  searchCompleted.value = true
  query.value = fixture.query
  collection.value = 'swin_v1'
  candidates.value = [fixture.candidate]
  selected.value = [fixture.candidate.source_id]
  activeId.value = fixture.candidate.source_id
  const enrichEvidence = (record: ResearchRecord): ResearchRecord => ({
    ...record,
    claims: record.claims.map(verdict => ({
      ...verdict,
      evidence: fixture.candidate.evidence.filter(item => verdict.claim.evidence_ids.includes(item.chunk_id)),
    })),
    fields: record.fields.map(field => ({
      ...field,
      claims: field.claims.map(verdict => ({
        ...verdict,
        evidence: fixture.candidate.evidence.filter(item => verdict.claim.evidence_ids.includes(item.chunk_id)),
      })),
    })),
  })
  const demoHistory: ResearchHistory = {
    screening: fixture.history.screening.map(enrichEvidence),
    extraction: fixture.history.extraction.map(enrichEvidence),
    diagnostics: [],
  }
  const screening = demoHistory.screening[0] ?? null
  const extraction = demoHistory.extraction[0] ?? null
  const card: CardResponse = {
    status: 'completed', candidate: fixture.candidate, screening, extraction,
    usage: { paid_calls: 0, prompt_tokens: 0, completion_tokens: 0, actual_cost_usd: null },
    high_confidence_fields: [], review_candidates: [], failure_code: null,
    stages: [], stop_reason: 'completed',
  }
  cards.value = { [fixture.candidate.source_id]: card }
  agentResult.value = null
  researchHistory.value = demoHistory
  historyError.value = ''
  historyType.value = 'extraction'
  const [oldVersion, newVersion] = selectLatestPair(
    historyForSubjectAndType(demoHistory, fixture.candidate.source_id, 'extraction'),
  )
  historyLeftId.value = oldVersion?.record_id ?? ''
  historyRightId.value = newVersion?.record_id ?? ''
  report.value = null
  demoReport.value = fixture.report
  proof.value = fixture.candidate.evidence[0] ?? null
  error.value = ''
}

async function exitDemo() {
  if (!savedLiveState) return
  const state = savedLiveState
  savedLiveState = null
  restoringSnapshot = true
  demoMode.value = false
  query.value = state.query
  searchCompleted.value = state.searchCompleted
  collection.value = state.collection
  candidates.value = state.candidates
  selected.value = state.selected
  activeId.value = state.activeId
  cards.value = state.cards
  report.value = state.report
  demoReport.value = ''
  proof.value = state.proof
  researchHistory.value = state.researchHistory
  historyError.value = state.historyError
  historyType.value = state.historyType
  historyLeftId.value = state.historyLeftId
  historyRightId.value = state.historyRightId
  error.value = state.error
  serviceOnline.value = state.serviceOnline
  agentResult.value = state.agentResult
  editingScreening.value = state.editingScreening
  editingExtraction.value = state.editingExtraction
  screeningDecision.value = state.screeningDecision
  screeningReason.value = state.screeningReason
  editFields.value = state.editFields
  reviewSearch.value = state.reviewSearch
  reviewEvidence.value = state.reviewEvidence
  reviewEdits.value = state.reviewEdits
  agentQuery.value = state.agentQuery
  agentClaimKind.value = state.agentClaimKind
  await nextTick()
  restoringSnapshot = false
}

async function retryHistory() {
  if (!active.value || demoMode.value) return
  const sourceId = active.value.source_id
  const requestId = ++historyRequestId
  historyBusy.value = true
  historyError.value = ''
  try {
    const loadedHistory = await getResearchHistory(sourceId)
    if (requestId !== historyRequestId || demoMode.value || activeId.value !== sourceId) return
    researchHistory.value = loadedHistory
    serviceOnline.value = true
    if (!researchHistory.value[historyType.value].length) {
      historyType.value = historyType.value === 'extraction' ? 'screening' : 'extraction'
    }
    const [oldVersion, newVersion] = selectLatestPair(
      historyForSubjectAndType(researchHistory.value, sourceId, historyType.value),
    )
    historyLeftId.value = oldVersion?.record_id ?? ''
    historyRightId.value = newVersion?.record_id ?? ''
  } catch (cause) {
    if (requestId !== historyRequestId || demoMode.value || activeId.value !== sourceId) return
    markApiFailure(cause)
    historyError.value = cause instanceof Error ? cause.message : '读取历史记录失败。'
  } finally {
    if (requestId === historyRequestId) historyBusy.value = false
  }
}

function stageLabel(stage: string): string {
  return ({ evidence_preparation: '证据准备', model_submission: '模型提交', result_validation: '结果校验', record_save: '记录保存' } as Record<string, string>)[stage] ?? stage
}

function stopReasonLabel(reason: string): string {
  return ({
    tool_submission_rejected: '模型未能提交符合约束的工具结果',
    model_request_failed: '模型请求未完成',
    model_unavailable: '生成服务不可用',
    model_timeout: '模型请求超时',
    budget_exhausted: '本次任务预算已用尽',
    record_save_failed: '模型已返回结果，但研究记录保存失败；请先检查历史记录',
  } as Record<string, string>)[reason] ?? reason
}

function changeLabel(change: string): string {
  return ({ added: '新增', removed: '删除', modified: '修改', unchanged: '未变化' } as Record<string, string>)[change] ?? change
}

function claimDetails(claims: ResearchRecord['claims'] | NonNullable<ResearchRecord['fields'][number]['claims']>) {
  return claims.map(claim => ({
    status: statusText(claim.status),
    quote: claim.claim.quote ?? null,
    statement: claim.claim.statement,
    location: claim.evidence[0] ? sourceLabel(claim.evidence[0]) : '记录中未保存证据位置',
  }))
}

function issue(message: string) {
  error.value = message
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function markApiFailure(cause: unknown) {
  serviceOnline.value = cause instanceof ApiError ? cause.status < 500 : false
}

function initializeReview(card: CardResponse) {
  reviewEdits.value = Object.fromEntries(card.review_candidates.map(item => [item.occurrence, {
    name: item.name,
    value: item.value,
    quote: item.quote,
    evidence_id: item.evidence_id,
  }]))
  reviewEvidence.value = []
}

async function searchPapers() {
  if (demoMode.value) return
  if (!query.value.trim()) return issue('请输入研究问题。')
  busy.value = 'search'
  error.value = ''
  report.value = null
  cards.value = {}
  try {
    const result = await discover(query.value.trim(), collection.value)
    searchCompleted.value = true
    serviceOnline.value = true
    candidates.value = result.candidates
    selected.value = result.candidates.length ? [result.candidates[0].source_id] : []
    activeId.value = result.candidates[0]?.source_id ?? null
    proof.value = result.candidates[0]?.evidence[0] ?? null
  } catch (cause) {
    searchCompleted.value = false
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '检索失败。')
  } finally {
    busy.value = null
  }
}

function toggleCandidate(candidate: Candidate) {
  if (demoMode.value) return
  activeId.value = candidate.source_id
  proof.value = candidate.evidence[0] ?? null
  if (selected.value.includes(candidate.source_id)) {
    selected.value = selected.value.filter(id => id !== candidate.source_id)
  } else if (selected.value.length < 4) {
    selected.value = [...selected.value, candidate.source_id]
  } else {
    error.value = '一次最多选择 4 篇论文。'
  }
}

async function createCard() {
  if (!active.value || demoMode.value) return
  busy.value = 'card'
  error.value = ''
  try {
    const result = await generateCard(query.value.trim(), active.value.collection, active.value.source_id)
    serviceOnline.value = true
    cards.value = { ...cards.value, [active.value.source_id]: result }
    initializeReview(result)
    editingScreening.value = false
    editingExtraction.value = false
    proof.value = result.extraction?.fields[0]?.claims[0]?.evidence[0] ?? active.value.evidence[0] ?? null
    await retryHistory()
  } catch (cause) {
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '信息卡生成失败。')
  } finally {
    busy.value = null
  }
}

async function restoreCard() {
  if (!active.value || demoMode.value) return
  busy.value = 'load'
  error.value = ''
  try {
    const result = await loadCard(query.value.trim(), active.value.collection, active.value.source_id)
    serviceOnline.value = true
    cards.value = { ...cards.value, [active.value.source_id]: result }
    initializeReview(result)
    proof.value = result.extraction?.fields[0]?.claims[0]?.evidence[0] ?? active.value.evidence[0] ?? null
    editingScreening.value = false
    editingExtraction.value = false
    await retryHistory()
  } catch (cause) {
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '读取已保存信息卡失败。')
  } finally {
    busy.value = null
  }
}

function beginScreeningEdit() {
  if (demoMode.value) return
  if (!activeCard.value?.screening) return
  screeningDecision.value = activeCard.value.screening.decision ?? 'hold'
  screeningReason.value = activeCard.value.screening.claims[0]?.claim.statement ?? ''
  editingScreening.value = true
  editingExtraction.value = false
}

async function saveScreening() {
  if (demoMode.value) return
  const paper = active.value
  const card = activeCard.value
  if (!paper || !card?.screening) return
  const reason = screeningReason.value.trim()
  if (!reason) return issue('请填写筛选理由。')
  const evidenceId = card.screening.claims[0]?.evidence[0]?.chunk_id ?? card.candidate.evidence[0]?.chunk_id
  if (!evidenceId) return issue('当前记录没有可引用的论文证据。')
  busy.value = 'screening'
  error.value = ''
  try {
    const screening = await reviseScreening(query.value.trim(), paper, card.screening.record_id, screeningDecision.value, reason, evidenceId)
    serviceOnline.value = true
    cards.value = { ...cards.value, [paper.source_id]: { ...card, screening } }
    editingScreening.value = false
    report.value = null
    await retryHistory()
  } catch (cause) {
    markApiFailure(cause)
    issue(`保存状态未确认。请先刷新历史，避免重复提交。${cause instanceof Error ? ` ${cause.message}` : ''}`)
  } finally {
    busy.value = null
  }
}

function beginExtractionEdit() {
  if (demoMode.value) return
  const extracted = activeCard.value?.extraction
  if (!extracted) return
  editFields.value = extracted.fields.map((field, originalIndex) => ({ name: field.name, value: field.value, originalIndex }))
  editingExtraction.value = true
  editingScreening.value = false
}

async function saveExtraction() {
  if (demoMode.value) return
  const paper = active.value
  const card = activeCard.value
  if (!paper || !card?.extraction) return
  const revised = editFields.value.flatMap(entry => {
    const name = entry.name
    const prior = card.extraction?.fields[entry.originalIndex]
    if (prior && entry.value === prior.value) return [{ name, value: prior.value, claims: prior.claims.map(verdict => verdict.claim) }]
    const value = entry.value.trim()
    if (!value) return []
    const evidence = prior?.claims[0]?.evidence[0] ?? card.candidate.evidence[0]
    if (!evidence) return []
    const verbatim = value.length <= 1000 && evidence.text.includes(value)
    return [{
      name,
      value,
      claims: [verbatim
        ? { statement: value, kind: 'verbatim' as const, evidence_ids: [evidence.chunk_id], quote: value }
        : { statement: value, kind: 'inference' as const, evidence_ids: [evidence.chunk_id] }],
    }]
  })
  if (!revised.length) return issue('至少保留一个字段，并为它关联论文证据。')
  busy.value = 'extraction'
  error.value = ''
  try {
    const extraction = await reviseExtraction(query.value.trim(), paper, card.extraction.record_id, revised)
    serviceOnline.value = true
    cards.value = { ...cards.value, [paper.source_id]: { ...card, extraction } }
    editingExtraction.value = false
    report.value = null
    await retryHistory()
  } catch (cause) {
    markApiFailure(cause)
    issue(`保存状态未确认。请先刷新历史，避免重复提交。${cause instanceof Error ? ` ${cause.message}` : ''}`)
  } finally {
    busy.value = null
  }
}

function evidenceFor(card: CardResponse, evidenceId: string): Evidence | undefined {
  return [...card.candidate.evidence, ...reviewEvidence.value].find(item => item.chunk_id === evidenceId)
}

function showEvidence(evidenceId: string) {
  const card = activeCard.value
  proof.value = card ? evidenceFor(card, evidenceId) ?? null : null
}

async function findReviewEvidence() {
  if (demoMode.value) return
  const paper = active.value
  if (!paper || !reviewSearch.value.trim()) return issue('请输入要在当前论文中查找的关键词。')
  busy.value = 'evidence'
  error.value = ''
  try {
    const result = await searchPaperEvidence(reviewSearch.value.trim(), paper.collection, paper.source_id)
    serviceOnline.value = true
    reviewEvidence.value = result.results
  } catch (cause) {
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '论文内证据搜索失败。')
  } finally {
    busy.value = null
  }
}

function useReviewEvidence(candidate: ReviewCandidate, evidence: Evidence) {
  const edit = reviewEdits.value[candidate.occurrence]
  if (!edit) return
  const valueOffset = edit.value.trim() ? evidence.text.indexOf(edit.value.trim()) : 0
  const quoteStart = valueOffset > 0 ? Math.max(0, valueOffset - 300) : 0
  const quote = evidence.text.slice(quoteStart, quoteStart + 1000)
  reviewEdits.value = { ...reviewEdits.value, [candidate.occurrence]: { ...edit, evidence_id: evidence.chunk_id, quote } }
  proof.value = evidence
}

function ignoreReviewCandidate(candidate: ReviewCandidate) {
  const card = activeCard.value
  const paper = active.value
  if (!card || !paper) return
  cards.value = { ...cards.value, [paper.source_id]: { ...card, review_candidates: card.review_candidates.filter(item => item.occurrence !== candidate.occurrence) } }
}

function addManualCandidate() {
  if (demoMode.value) return
  const card = activeCard.value
  const paper = active.value
  if (!card || !paper) return
  const used = [
    ...card.high_confidence_fields.map(item => item.occurrence),
    ...card.review_candidates.map(item => item.occurrence),
  ]
  const occurrence = used.length ? Math.max(...used) + 1 : 0
  const evidenceId = reviewEvidence.value[0]?.chunk_id ?? card.candidate.evidence[0]?.chunk_id ?? ''
  const candidate: ReviewCandidate = {
    occurrence,
    source_id: paper.source_id,
    name: 'task',
    value: '',
    quote: '',
    evidence_id: evidenceId,
    reason_codes: ['user_created'],
    reason: '模型未给出可用条目，请在当前论文内搜索并人工补录。',
    allowed_actions: ['open_evidence', 'search_same_paper', 'edit_and_save', 'ignore'],
  }
  cards.value = {
    ...cards.value,
    [paper.source_id]: { ...card, review_candidates: [...card.review_candidates, candidate] },
  }
  reviewEdits.value = {
    ...reviewEdits.value,
    [occurrence]: { name: 'task', value: '', quote: '', evidence_id: evidenceId },
  }
}

async function saveReviewCandidate(candidate: ReviewCandidate) {
  if (demoMode.value) return
  const paper = active.value
  const card = activeCard.value
  const edit = reviewEdits.value[candidate.occurrence]
  if (!paper || !card || !edit) return
  const evidence = evidenceFor(card, edit.evidence_id)
  if (!evidence || evidence.source.source_id !== paper.source_id) return issue('请选择当前论文中的证据。')
  const value = edit.value.trim()
  const quote = edit.quote.trim()
  if (!value || !quote) return issue('字段值和原文引文不能为空。')
  const existing = card.extraction?.fields.map(field => ({ name: field.name, value: field.value, claims: field.claims.map(verdict => verdict.claim) })) ?? card.high_confidence_fields.map(field => ({
    name: field.name,
    value: field.value,
    claims: [{ statement: field.value, kind: 'verbatim', evidence_ids: [field.evidence_id], quote: field.quote }],
  }))
  const claim = evidence.text.includes(quote) && quote.includes(value)
    ? { statement: value, kind: 'verbatim' as const, evidence_ids: [evidence.chunk_id], quote }
    : { statement: value, kind: 'inference' as const, evidence_ids: [evidence.chunk_id] }
  const replacement = { name: edit.name, value, claims: [claim] }
  const revised = [...existing]
  if (card.status === 'completed' && card.extraction && candidate.occurrence < revised.length) revised[candidate.occurrence] = replacement
  else revised.push(replacement)
  busy.value = 'extraction'
  error.value = ''
  try {
    const extraction = await reviseExtraction(query.value.trim(), paper, card.extraction?.record_id ?? null, revised)
    serviceOnline.value = true
    cards.value = {
      ...cards.value,
      [paper.source_id]: {
        ...card,
        extraction,
        review_candidates: card.review_candidates.filter(item => item.occurrence !== candidate.occurrence),
      },
    }
    report.value = null
    await retryHistory()
  } catch (cause) {
    markApiFailure(cause)
    issue(`保存状态未确认。请先刷新历史，避免重复提交。${cause instanceof Error ? ` ${cause.message}` : ''}`)
  } finally {
    busy.value = null
  }
}

async function makeComparison() {
  if (demoMode.value) return
  if (comparisonIds.value.length < 2) return issue('请先为至少两篇已选论文生成实验信息卡。')
  busy.value = 'compare'
  error.value = ''
  try {
    report.value = await compareCards(comparisonIds.value)
    serviceOnline.value = true
  } catch (cause) {
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '对照报告生成失败。')
  } finally {
    busy.value = null
  }
}

async function checkReproduction() {
  if (demoMode.value) return
  if (!agentQuery.value.trim()) return issue('请输入需要核查的代码或配置问题。')
  busy.value = 'agent'
  error.value = ''
  agentResult.value = null
  try {
    agentResult.value = await runAgent(agentQuery.value.trim(), [agentClaimKind.value])
    serviceOnline.value = true
  } catch (cause) {
    markApiFailure(cause)
    issue(cause instanceof Error ? cause.message : '复现核查失败。')
  } finally {
    busy.value = null
  }
}

function sourceLabel(item: Evidence): string {
  const location = item.source.location
  if (location.page) return `第 ${location.page} 页`
  if (location.line_start) return `第 ${location.line_start}–${location.line_end ?? location.line_start} 行`
  if (location.section_index !== undefined) return `章节 ${Number(location.section_index) + 1} · 段落 ${Number(location.paragraph_index ?? 0) + 1}`
  return '正文位置'
}

function paperUrl(sourceId: string): string | null {
  if (sourceId.startsWith('qasper:')) return `https://arxiv.org/abs/${sourceId.slice(7)}`
  if (sourceId === 'src:21e757794f07f8f043ac') return 'https://arxiv.org/abs/2103.14030v2'
  return null
}

function statusText(status: ClaimStatus): string {
  return {
    supported: '原文匹配',
    requires_review: '待人工复核',
    insufficient_evidence: '证据不足',
    blocked_by_precondition: '前置条件阻断',
  }[status]
}

function saveReport() {
  if (!report.value) return
  const file = new Blob([report.value.markdown], { type: 'text/markdown;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(file)
  link.download = '复现有据-对照报告.md'
  link.click()
  URL.revokeObjectURL(link.href)
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#top" aria-label="复现有据首页">
        <BookOpenText :size="30" :stroke-width="1.65" />
        <span><strong>复现有据</strong><small>让研究结论有据可循</small></span>
      </a>
      <nav aria-label="工作区导航">
        <a href="#papers" class="nav-link"><FileSearch :size="19" />论文筛选</a>
        <a href="#card" class="nav-link"><ClipboardList :size="19" />实验信息卡</a>
        <a href="#comparison" class="nav-link"><GitCompareArrows :size="19" />对照报告</a>
        <a href="#reproduction" class="nav-link"><ShieldCheck :size="19" />复现核查</a>
      </nav>
      <p class="sidebar-foot">基于原文证据<br />支持可复核的研究</p>
    </aside>

    <main id="top" class="main-area">
      <header class="page-header">
        <div>
          <h1>从问题到可核查的研究结论</h1>
          <p>检索相关论文，提取实验信息，基于原文证据进行对照与核查。</p>
        </div>
        <div class="connection" :class="{ offline: serviceOnline === false }">
          <span class="connection-dot" />{{ serviceOnline === null ? '未检测' : serviceOnline ? '服务已连接' : '服务未连接' }}
        </div>
      </header>

      <div v-if="demoMode" class="demo-banner" role="status">
        <div><strong>预置演示数据 · 只读</strong><span>单篇 Swin 论文快照，加载与浏览不访问后端、模型或本地研究记录。</span></div>
        <button type="button" class="secondary-button" @click="exitDemo">退出演示</button>
      </div>

      <div v-if="error" class="error-banner" role="alert"><AlertCircle :size="18" /><span>{{ error }}</span><button v-if="!demoMode" class="text-button" type="button" @click="loadDemoCase">查看只读演示</button><button type="button" aria-label="关闭错误" @click="error = ''"><X :size="16" /></button></div>

      <div class="workspace-grid">
        <div class="content-column">
          <section id="papers" class="search-section" aria-labelledby="papers-title">
            <div class="section-heading"><div><p class="section-number">01 / 论文筛选</p><h2 id="papers-title">找到值得细读的论文</h2></div><span>来源限定在已建索引语料</span></div>
            <form class="search-form" @submit.prevent="searchPapers">
              <label class="search-input"><Search :size="19" /><input v-model="query" maxlength="1000" aria-label="研究问题" placeholder="输入研究问题或筛选条件" /></label>
              <label class="collection-select"><span class="sr-only">语料库</span><select v-model="collection" :disabled="demoMode"><option value="swin_v1">Swin Transformer</option><option value="vision_mamba_v1">Vision Mamba (Vim)</option><option value="qasper_train_v1">QASPER train · 方法示例</option></select></label>
              <button class="primary-button" type="submit" :disabled="demoMode || busy !== null"><LoaderCircle v-if="busy === 'search'" class="spin" :size="18" /><Search v-else :size="18" />{{ busy === 'search' ? '检索中' : '检索论文' }}</button>
              <button class="secondary-button demo-load-button" type="button" :disabled="busy !== null" @click="loadDemoCase"><BookOpenText :size="17" />载入演示案例</button>
            </form>
            <p v-if="demoMode" class="readonly-note">当前演示案例为只读快照；退出后可恢复在线检索与编辑。</p>
            <p class="collection-note">{{ collection === 'swin_v1' ? 'Swin 固定论文版本，用于视觉模型深度核查。' : collection === 'vision_mamba_v1' ? 'Vision Mamba 论文与固定 commit 源码组成独立语料；可生成证据卡并与 Swin 做字段对照。' : 'QASPER train 提供多论文方法演示；这些论文不代表视觉论文库。' }}</p>
            <div v-if="!candidates.length" class="empty-result"><FileSearch :size="25" /><p>{{ searchCompleted ? '没有找到符合条件的论文；可以修改关键词后重新检索，或查看只读演示。' : '输入问题并检索，候选论文将在这里出现。' }}</p><button v-if="searchCompleted" class="text-button" type="button" @click="loadDemoCase">载入演示案例</button></div>
            <div v-else class="candidate-list">
              <div class="result-caption">找到 {{ candidates.length }} 篇候选论文 <span>选择论文后生成可核查的信息卡</span></div>
              <article v-for="candidate in candidates" :key="candidate.source_id" class="candidate-row" :class="{ active: activeId === candidate.source_id }">
                <label class="candidate-choice"><input type="checkbox" :checked="selected.includes(candidate.source_id)" :disabled="demoMode" @change="toggleCandidate(candidate)" /><span class="checkmark"><Check :size="13" /></span><span class="sr-only">选择 {{ candidate.title }}</span></label>
                <button type="button" class="candidate-main" @click="activeId = candidate.source_id; proof = candidate.evidence[0] ?? null">
                  <strong>{{ candidate.title }}</strong><small>{{ candidate.source_id }} · {{ candidate.source_version }}</small>
                  <span>{{ candidate.evidence[0]?.text.slice(0, 175) || '暂无摘要片段' }}{{ candidate.evidence[0]?.text.length > 175 ? '…' : '' }}</span>
                </button>
                <button type="button" class="text-button evidence-action" @click="proof = candidate.evidence[0] ?? null">查看证据 <ExternalLink :size="15" /></button>
              </article>
            </div>
          </section>

          <section id="card" class="paper-panel card-section" aria-labelledby="card-title">
            <div class="panel-header"><div><p class="section-number">02 / 实验信息卡</p><h2 id="card-title">{{ active?.title || '选择论文后整理信息' }}</h2></div><div class="panel-actions"><button class="text-button" type="button" :disabled="!active || demoMode || busy !== null" @click="restoreCard"><LoaderCircle v-if="busy === 'load'" class="spin" :size="16" /><FolderOpen v-else :size="16" />{{ busy === 'load' ? '读取中' : '读取已存卡' }}</button><button class="secondary-button" type="button" :disabled="!active || demoMode || busy !== null" @click="createCard"><LoaderCircle v-if="busy === 'card'" class="spin" :size="17" /><FileText v-else :size="17" />{{ busy === 'card' ? '生成中' : '从原文生成' }}</button></div></div>
            <p v-if="demoMode" class="readonly-note">只读演示：生成、修订、论文内搜索和 Agent 调用已停用。</p>
            <div v-if="activeCard?.screening" class="screening-line"><span>筛选决定：{{ activeCard.screening.decision === 'include' ? '纳入' : activeCard.screening.decision === 'exclude' ? '排除' : '待定' }}</span><span>理由：{{ activeCard.screening.claims[0]?.claim.statement }}</span><em>待人工复核</em></div>
            <div v-else-if="activeCard" class="screening-line review-alert"><span>模型输出需要复核</span><span>{{ activeCard.failure_code || '未形成可提交的信息卡' }}</span><em>请在同一论文内查证</em></div>
            <div v-if="activeCard" class="card-usage"><span v-if="demoMode">预置演示数据 · 本地快照，不代表模型调用</span><span v-else-if="activeCard.usage.paid_calls">本次生成：{{ activeCard.usage.paid_calls }} 次模型调用 · {{ activeCard.usage.prompt_tokens }} 输入 token · {{ activeCard.usage.completion_tokens }} 输出 token · {{ activeCard.usage.actual_cost_usd === null ? '实际费用未提供' : activeCard.usage.actual_cost_usd }}</span><span v-else>读取已存记录：本次未调用模型</span><span v-if="activeCard.stages.length" class="stage-list">{{ activeCard.stages.map(stage => `${stageLabel(stage.stage)}：${stage.status === 'completed' ? '完成' : stage.status === 'failed' ? '失败' : '未执行'}`).join(' → ') }}</span><span v-if="activeCard.stop_reason !== 'completed'">停止原因：{{ stopReasonLabel(activeCard.stop_reason) }}</span></div>
            <div v-if="activeCard" class="revision-actions"><span>{{ activeCard.screening ? `当前筛选版本 ${activeCard.screening.record_id.slice(0, 8)}` : '尚无已提交筛选记录' }}{{ activeCard.extraction ? ` · 字段版本 ${activeCard.extraction.record_id.slice(0, 8)}` : '' }}</span><button type="button" class="text-button" :disabled="demoMode || !activeCard.screening || busy !== null" @click="beginScreeningEdit"><PencilLine :size="15" />修订筛选</button><button type="button" class="text-button" :disabled="demoMode || !activeCard.extraction || busy !== null" @click="beginExtractionEdit"><PencilLine :size="15" />修订字段</button></div>
            <form v-if="editingScreening" class="revision-form" @submit.prevent="saveScreening"><strong>筛选人工修订</strong><p>新记录会引用当前论文证据，并保留上一版本；筛选理由仍标记为待人工复核。</p><label>决定<select v-model="screeningDecision"><option value="include">纳入</option><option value="exclude">排除</option><option value="hold">待定</option></select></label><label>理由<textarea v-model="screeningReason" maxlength="2000" rows="3" /></label><div class="revision-buttons"><button type="button" class="text-button" @click="editingScreening = false">取消</button><button type="submit" class="secondary-button" :disabled="busy !== null"><Save :size="15" />{{ busy === 'screening' ? '保存中' : '保存新版本' }}</button></div></form>
            <section v-if="activeCard?.high_confidence_fields.length" class="confidence-section"><div class="confidence-heading"><strong>可直接使用的高置信字段</strong><span>同论文证据 · 连续原文 · 无确定性类型冲突</span></div><div v-for="item in activeCard.high_confidence_fields" :key="`high-${item.occurrence}`" class="confidence-row"><strong>{{ fields.find(([name]) => name === item.name)?.[1] }}</strong><span>{{ item.value }}</span><button type="button" class="inline-proof" @click="showEvidence(item.evidence_id)">查看原文</button></div></section>
            <section v-if="activeCard && (activeCard.status === 'review_required' || activeCard.review_candidates.length)" class="review-section"><div class="confidence-heading"><strong>需要你确认的候选字段</strong><span>可在当前论文内搜索，不会跨论文取证</span></div><form class="paper-search" @submit.prevent="findReviewEvidence"><input v-model="reviewSearch" maxlength="1000" placeholder="在当前论文中搜索数据集、指标或结果" aria-label="论文内搜索" /><button type="submit" class="text-button" :disabled="busy !== null"><Search :size="15" />{{ busy === 'evidence' ? '搜索中' : '论文内搜索' }}</button></form><div v-if="reviewEvidence.length" class="review-evidence-list"><button v-for="item in reviewEvidence" :key="item.chunk_id" type="button" @click="proof = item"><strong>{{ sourceLabel(item) }}</strong><span>{{ item.text.slice(0, 150) }}{{ item.text.length > 150 ? '…' : '' }}</span></button></div><div v-if="!activeCard.review_candidates.length" class="manual-review-empty"><span>模型没有留下可修订条目。请搜索当前论文，再手动添加字段。</span><button type="button" class="secondary-button" @click="addManualCandidate">手动添加字段</button></div><article v-for="candidate in activeCard.review_candidates" :key="`review-${candidate.occurrence}`" class="review-candidate"><div class="review-reason"><strong>候选 {{ candidate.occurrence + 1 }}</strong><span>{{ candidate.reason }}</span></div><div class="review-grid"><label>字段类型<select v-model="reviewEdits[candidate.occurrence].name"><option v-for="[name, label] in fields" :key="name" :value="name">{{ label }}</option></select></label><label>字段值<input v-model="reviewEdits[candidate.occurrence].value" maxlength="2000" /></label><label class="review-quote">原文引文<textarea v-model="reviewEdits[candidate.occurrence].quote" maxlength="1000" rows="3" /></label></div><div class="review-source"><span>证据：{{ reviewEdits[candidate.occurrence].evidence_id }}</span><button type="button" class="text-button" @click="showEvidence(reviewEdits[candidate.occurrence].evidence_id)">查看当前证据</button></div><div v-if="reviewEvidence.length" class="review-buttons"><button v-for="item in reviewEvidence" :key="`${candidate.occurrence}-${item.chunk_id}`" type="button" class="text-button" @click="useReviewEvidence(candidate, item)">改用 {{ sourceLabel(item) }}</button></div><div class="review-buttons"><button type="button" class="text-button" @click="ignoreReviewCandidate(candidate)">忽略候选</button><button type="button" class="secondary-button" :disabled="busy !== null" @click="saveReviewCandidate(candidate)"><Save :size="15" />保存为新版本</button></div></article></section>
            <div class="field-table" role="table" aria-label="实验信息卡">
              <div class="field-head" role="row"><span>信息项</span><span>内容与来源</span><span>核查状态</span></div>
              <template v-for="[name, label] in fields" :key="name">
                <div v-for="(entry, index) in activeCard?.extraction?.fields.filter(field => field.name === name) ?? []" :key="`${name}-${index}`" class="field-row" role="row">
                  <strong>{{ label }} · {{ index + 1 }}</strong>
                  <div class="field-value">{{ entry.value }}<button type="button" class="inline-proof" @click="proof = entry.claims[0]?.evidence[0] ?? null">查看证据</button></div>
                  <span class="claim-status" :class="entry.claims[0]?.status">{{ entry.claims[0] ? statusText(entry.claims[0].status) : '待复核' }}</span>
                </div>
                <div v-if="!activeCard?.extraction?.fields.some(field => field.name === name)" class="field-row" role="row"><strong>{{ label }}</strong><span class="muted">{{ activeCard ? '未提取' : '待生成' }}</span><span>—</span></div>
              </template>
            </div>
            <form v-if="editingExtraction" class="revision-form" @submit.prevent="saveExtraction"><strong>实验字段人工修订</strong><p>留空可移除字段。新增或改写内容若不在所引原文中，将标记为待人工复核；保存后生成新的字段版本。</p><div class="revision-fields"><label v-for="(entry, index) in editFields" :key="index">{{ fields.find(([name]) => name === entry.name)?.[1] }} · {{ index + 1 }}<input v-model="entry.value" maxlength="2000" :aria-label="`修订${entry.name}条目${index + 1}`" /></label></div><div class="revision-buttons"><button v-for="[name, label] in fields" :key="name" type="button" class="text-button" :disabled="editFields.length >= 36" @click="editFields.push({ name, value: '', originalIndex: -1 })">添加{{ label }}</button></div><div class="revision-buttons"><button type="button" class="text-button" @click="editingExtraction = false">取消</button><button type="submit" class="secondary-button" :disabled="busy !== null"><Save :size="15" />{{ busy === 'extraction' ? '保存中' : '保存新版本' }}</button></div></form>
            <p class="panel-note">“原文匹配”只表示所引文字在原文中；字段归类与研究解释须人工核对。</p>
          </section>

          <section class="paper-panel history-section" aria-labelledby="history-title">
            <div class="panel-header"><div><p class="section-number">02.5 / 记录历史</p><h2 id="history-title">研究记录版本与差异</h2></div><span v-if="demoMode" class="demo-chip">预置演示数据</span><button v-else-if="active" class="text-button" type="button" :disabled="historyBusy" @click="retryHistory"><LoaderCircle v-if="historyBusy" class="spin" :size="15" /><FolderOpen v-else :size="15" />{{ historyBusy ? '读取中' : '刷新历史' }}</button></div>
            <p v-if="!active" class="empty-inline">选择一篇论文后查看其筛选与提取记录。</p>
            <div v-else-if="historyError" class="inline-error" role="alert"><span>历史记录读取失败：{{ historyError }}</span><button type="button" class="text-button" @click="retryHistory">重试只读请求</button></div>
            <p v-else-if="historyBusy && !researchHistory" class="empty-inline">正在读取已保存的研究记录…</p>
            <p v-else-if="researchHistory && !researchHistory.screening.length && !researchHistory.extraction.length" class="empty-inline">这篇论文还没有已保存的研究卡。生成或提交后，历史版本会显示在这里。</p>
            <template v-else-if="researchHistory">
              <div class="history-groups">
                <div><strong>筛选记录</strong><span>{{ researchHistory.screening.length }} 版</span><ol><li v-for="record in researchHistory.screening" :key="record.record_id"><time>{{ new Date(record.created_at).toLocaleString() }}</time><span>{{ record.decision }} · {{ record.record_id.slice(0, 8) }}</span><small>修订自：{{ record.revision_of?.slice(0, 8) ?? '初始版本' }}</small></li><li v-if="!researchHistory.screening.length" class="empty-inline">暂无筛选记录</li></ol></div>
                <div><strong>提取记录</strong><span>{{ researchHistory.extraction.length }} 版</span><ol><li v-for="record in researchHistory.extraction" :key="record.record_id"><time>{{ new Date(record.created_at).toLocaleString() }}</time><span>{{ record.fields.length }} 个字段 · {{ record.record_id.slice(0, 8) }}</span><small>修订自：{{ record.revision_of?.slice(0, 8) ?? '初始版本' }}</small></li><li v-if="!researchHistory.extraction.length" class="empty-inline">暂无提取记录</li></ol></div>
              </div>
              <p v-if="researchHistory.diagnostics.length" class="history-warning">有 {{ researchHistory.diagnostics.length }} 个损坏或不可读取记录文件，其他有效记录仍可查看。</p>
              <div class="diff-controls"><label>记录类型<select v-model="historyType" @change="historyLeftId = historyRecords[1]?.record_id ?? ''; historyRightId = historyRecords[0]?.record_id ?? ''"><option value="extraction">提取记录</option><option value="screening">筛选记录</option></select></label><label>旧版本<select v-model="historyLeftId"><option v-for="record in historyRecords" :key="record.record_id" :value="record.record_id">{{ new Date(record.created_at).toLocaleString() }} · {{ record.record_id.slice(0, 8) }}</option></select></label><label>新版本<select v-model="historyRightId"><option v-for="record in historyRecords" :key="record.record_id" :value="record.record_id">{{ new Date(record.created_at).toLocaleString() }} · {{ record.record_id.slice(0, 8) }}</option></select></label></div>
              <p v-if="historyRecords.length < 2" class="empty-inline">至少需要同类型的两个版本才能比较。</p>
              <p v-else-if="historyLeftId === historyRightId" class="empty-inline">请选择两个不同版本进行比较。</p>
              <div v-else-if="historyDiff.length" class="diff-table-wrap"><table class="diff-table"><thead><tr><th>变化</th><th>字段</th><th>旧版本</th><th>新版本</th><th>原文证据</th></tr></thead><tbody><tr v-for="row in historyDiff" :key="row.key"><td><span class="change-chip" :class="row.change">{{ changeLabel(row.change) }}</span><small v-if="row.needsReview" class="ambiguous-note">同名多条目配对，需人工确认</small></td><th>{{ row.label }}</th><td>{{ row.before?.value ?? '—' }}<small v-for="detail in row.before ? claimDetails(row.before.claims) : []" :key="`old-${row.key}-${detail.statement}`">{{ detail.status }} · {{ detail.quote ? `原文引文：“${detail.quote}”` : `研究陈述：${detail.statement}（未附原文引文）` }} · {{ detail.location }}</small></td><td>{{ row.after?.value ?? '—' }}<small v-for="detail in row.after ? claimDetails(row.after.claims) : []" :key="`new-${row.key}-${detail.statement}`">{{ detail.status }} · {{ detail.quote ? `原文引文：“${detail.quote}”` : `研究陈述：${detail.statement}（未附原文引文）` }} · {{ detail.location }}</small></td><td><button v-for="evidence in [...(row.before?.claims ?? []), ...(row.after?.claims ?? [])].flatMap(claim => claim.evidence)" :key="evidence.chunk_id" class="inline-proof" type="button" @click="proof = evidence">{{ sourceLabel(evidence) }}</button><span v-if="![...(row.before?.claims ?? []), ...(row.after?.claims ?? [])].some(claim => claim.evidence.length)" class="muted">记录未携带证据对象</span></td></tr></tbody></table></div>
            </template>
          </section>

          <section id="comparison" class="paper-panel comparison-section" aria-labelledby="comparison-title">
            <div class="panel-header"><div><p class="section-number">03 / 对照报告</p><h2 id="comparison-title">{{ demoMode ? '单篇论文研究记录快照' : '比较实验设置，保留不可比条件' }}</h2></div><button v-if="!demoMode" class="secondary-button" type="button" :disabled="comparisonIds.length < 2 || busy !== null" @click="makeComparison"><LoaderCircle v-if="busy === 'compare'" class="spin" :size="17" /><GitCompareArrows v-else :size="17" />生成对照报告</button><span v-else class="demo-chip">预置单篇快照</span></div>
            <div v-if="demoMode && demoReport" class="report-box"><p class="readonly-note">这是单篇研究记录快照，不是论文间比较或性能排名。</p><div class="markdown-body" v-html="DOMPurify.sanitize(markdown.render(demoReport))" /></div>
            <p v-if="!demoMode" class="comparison-hint">已选择 {{ selected.length }} 篇论文，其中 {{ comparisonIds.length }} 篇已有信息卡。需要至少两张卡片才能比较。</p>
            <div v-if="report" class="report-box"><div class="report-toolbar"><span>{{ report.comparable ? '关键条件字面一致，仍不自动排名' : '数据集、指标或输入条件不完整，不自动排名' }}</span><button type="button" class="text-button" @click="saveReport"><ArrowDownToLine :size="17" />下载 Markdown</button></div><div class="markdown-body" v-html="reportHtml" /></div>
            <div v-else-if="!demoMode" class="report-empty"><GitCompareArrows :size="23" /><p>为两篇以上论文生成实验卡后，这里会显示带原文位置的对照报告。</p></div>
          </section>

          <section id="reproduction" class="paper-panel reproduction-section" aria-labelledby="reproduction-title">
            <div class="panel-header"><div><p class="section-number">04 / 复现核查</p><h2 id="reproduction-title">对代码条件做证据核查</h2></div><ShieldCheck :size="22" /></div>
            <p>限定 Swin 官方固定版本。Agent 会检索、提交结构化结论，程序核查后再生成引用回答；一次任务可能产生付费模型调用。</p>
            <div class="agent-form"><textarea v-model="agentQuery" maxlength="4096" placeholder="例如：给定 PatchMerging.forward 的 H=8、W=8、L=64，前置断言是否通过？" aria-label="复现核查问题" /><div><select v-model="agentClaimKind" aria-label="核查类型"><option value="code_execution">代码前置条件</option><option value="inference">研究推断</option><option value="numeric">数值计算</option><option value="verbatim">原文引文</option></select><button class="primary-button" type="button" :disabled="demoMode || busy !== null" @click="checkReproduction"><LoaderCircle v-if="busy === 'agent'" class="spin" :size="17" /><ShieldCheck v-else :size="17" />{{ busy === 'agent' ? '核查中' : demoMode ? '只读演示' : '运行核查' }}</button></div></div>
            <div v-if="agentResult" class="agent-result"><div class="agent-result-head"><strong>任务状态：{{ agentResult.status }}</strong><span>{{ agentResult.usage.paid_calls }} 次模型调用 · {{ agentResult.usage.actual_cost_usd === null ? '实际费用未提供' : agentResult.usage.actual_cost_usd }}</span></div><p v-if="agentResult.workflow_stages.length">{{ agentResult.workflow_stages.map(stage => `${stage.stage}: ${stage.status}`).join(' → ') }}</p><div v-if="agentResult.answer" class="answer-text">{{ agentResult.answer.answer }}</div><p v-else>未生成回答：{{ agentResult.stop_reason }}</p><div v-for="artifact in agentResult.artifacts" :key="artifact.kind"><div v-for="verdict in artifact.verdicts || []" :key="verdict.claim.statement" class="verdict-row"><span :class="verdict.status">{{ statusText(verdict.status) }}</span><span>{{ verdict.claim.statement }}</span><button v-if="verdict.evidence[0]" type="button" class="inline-proof" @click="proof = verdict.evidence[0]">原文</button></div></div></div>
          </section>
        </div>

        <aside class="evidence-panel" aria-label="原文证据"><div class="evidence-title"><div><p class="section-number">原文证据</p><h2>当前选中来源</h2></div><button type="button" :disabled="!proof" aria-label="关闭证据" @click="proof = null"><X :size="18" /></button></div>
          <div v-if="proof" class="proof-content"><p class="proof-id">{{ proof.source.source_id }}</p><dl><dt>路径</dt><dd>{{ proof.source.source_path }}</dd><dt>版本</dt><dd>{{ proof.source.source_version }}</dd><dt>位置</dt><dd>{{ sourceLabel(proof) }}</dd></dl><blockquote>{{ proof.text }}</blockquote><a v-if="paperUrl(proof.source.source_id)" :href="paperUrl(proof.source.source_id)!" target="_blank" rel="noopener noreferrer" class="source-link">打开论文来源 <ExternalLink :size="16" /></a><p v-else class="proof-note">已记录原始文件路径与行号；请在项目语料中核对。</p></div>
          <div v-else class="proof-empty"><BookOpenText :size="26" /><p>点击候选或字段旁的“查看证据”，在这里阅读原文、位置与版本。</p></div>
          <div class="inspector-foot"><CheckCheck :size="16" /> 检索与引文只使用当前限定的语料版本</div>
        </aside>
      </div>
    </main>
  </div>
</template>
