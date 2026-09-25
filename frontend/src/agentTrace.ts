import type { AgentResponse, AgentTrajectoryEvent, Evidence } from './types'

const taskStatuses: Record<string, string> = {
  completed: '已完成',
  insufficient_evidence: '证据不足',
  review_required: '需要人工复核',
  budget_exhausted: '预算耗尽',
  no_progress: '未能继续推进',
  failed: '任务失败',
  timed_out: '已超时',
}

const stopReasons: Record<string, string> = {
  final_answer_generated: '已生成最终回答',
  planner_step_limit_no_automatic_answer: '规划轮次用尽，未自动补写回答',
  paid_or_tool_budget_exhausted: '调用预算已用尽',
  task_or_model_timeout_no_retry: '任务或模型超时，未自动重试',
  repeated_or_invalid_actions: '重复或无效操作，已停止',
  model_index_or_tool_validation_failed: '模型、索引或工具参数校验失败',
}

const toolNames: Record<string, string> = {
  search_evidence: '检索语料',
  read_evidence: '读取证据',
  trace_config: '追踪配置',
  calculate: '数值计算',
  verify_claims: '核查结论',
  record_screening: '保存筛选记录',
  record_extraction: '保存信息卡',
  build_research_report: '生成研究报告',
  submit_claims: '提交结论核查',
  gen_answer: '生成回答',
  complete: '结束任务',
}

const eventStatuses: Record<string, string> = {
  planned: '已返回工具选择',
  completed: '已完成',
  cached: '命中缓存',
  failed: '失败',
}

export interface DisplayAgentEvent {
  key: string
  title: string
  statusLabel: string
  statusCode: string
  parameterSummary: string
  resultSummary: string
}

function bounded(value: string | null | undefined): string {
  if (!value) return ''
  return value.length > 240 ? `${value.slice(0, 239)}…` : value
}

export function agentStatusLabel(status: string): string {
  return taskStatuses[status] ?? `其他状态：${status}`
}

export function stopReasonLabel(reason: string): string {
  return stopReasons[reason] ?? `停止原因：${reason}`
}

export function eventStatusLabel(status: string | null | undefined): string {
  if (!status) return '状态未提供'
  return eventStatuses[status] ?? `其他状态：${status}`
}

export function displayTrajectory(events: readonly AgentTrajectoryEvent[]): DisplayAgentEvent[] {
  return events.map((event, index) => ({
    key: `${event.turn}-${event.event}-${index}`,
    title: event.event === 'planning'
      ? `第 ${event.turn} 轮工具规划`
      : toolNames[event.tool ?? ''] ?? '未知工具',
    statusLabel: eventStatusLabel(event.status),
    statusCode: event.status ?? 'unavailable',
    parameterSummary: bounded(event.parameter_summary),
    resultSummary: bounded(event.result_summary),
  }))
}

export function citedEvidence(response: AgentResponse | null | undefined): Evidence[] {
  return response?.answer?.citations.map(citation => citation.evidence) ?? []
}
