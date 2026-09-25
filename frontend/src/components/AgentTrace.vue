<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, CircleCheck, LoaderCircle, MinusCircle } from '@lucide/vue'
import {
  agentStatusLabel,
  citedEvidence,
  displayTrajectory,
  stopReasonLabel,
} from '../agentTrace'
import type { AgentResponse, Evidence } from '../types'

const props = withDefaults(defineProps<{
  response: AgentResponse | null
  query?: string
  loading?: boolean
  mode?: 'live' | 'replay'
}>(), {
  query: '',
  loading: false,
  mode: 'live',
})

const emit = defineEmits<{
  'open-evidence': [evidence: Evidence]
}>()

const events = computed(() => displayTrajectory(props.response?.trajectory ?? []))
const citations = computed(() => citedEvidence(props.response))

function locationLabel(evidence: Evidence): string {
  const location = evidence.source.location
  if (typeof location.page === 'number') return `第 ${location.page} 页`
  if (typeof location.line_start === 'number') {
    const end = typeof location.line_end === 'number' ? `–${location.line_end}` : ''
    return `第 ${location.line_start}${end} 行`
  }
  if (typeof location.paragraph_index === 'number') return `第 ${location.paragraph_index} 段`
  return '来源位置已记录'
}

function claimStatusLabel(status: string): string {
  return ({
    supported: '证据支持',
    requires_review: '需要复核',
    insufficient_evidence: '证据不足',
    blocked_by_precondition: '前置条件阻断',
  } as Record<string, string>)[status] ?? `其他状态：${status}`
}
</script>

<template>
  <section class="agent-trace" aria-labelledby="agent-trace-title">
    <header class="agent-trace-heading">
      <div>
        <p class="section-number">AGENT / 可审计执行轨迹</p>
        <h3 id="agent-trace-title">从工具调用到有据回答</h3>
      </div>
      <span class="trace-mode" :class="mode">
        {{ mode === 'replay' ? '预置演示数据 · 只读' : '在线执行结果' }}
      </span>
    </header>

    <div v-if="query" class="trace-request">
      <span>本次研究问题</span>
      <p>{{ query }}</p>
    </div>

    <div v-if="loading" class="trace-wait" role="status" aria-live="polite">
      <LoaderCircle class="spin" :size="19" />
      <span>请求已提交，等待服务端返回 Agent 轨迹</span>
    </div>

    <template v-else-if="response">
      <div class="trace-summary">
        <div>
          <span class="trace-summary-label">任务状态</span>
          <strong>{{ agentStatusLabel(response.status) }}</strong>
          <span class="trace-code">{{ response.status }}</span>
        </div>
        <div>
          <span class="trace-summary-label">模型调用</span>
          <strong>{{ response.usage.paid_calls }} 次</strong>
          <span class="trace-code">{{ response.usage.prompt_tokens }} 输入 / {{ response.usage.completion_tokens }} 输出 token</span>
        </div>
        <div>
          <span class="trace-summary-label">停止原因</span>
          <strong>{{ stopReasonLabel(response.stop_reason) }}</strong>
        </div>
      </div>

      <div v-if="response.planner_model || response.answer_model" class="trace-models">
        <span v-if="response.planner_model">规划模型：{{ response.planner_model }}</span>
        <span v-if="response.answer_model">回答模型：{{ response.answer_model }}</span>
        <span>{{ response.usage.actual_cost_usd === null ? '实际费用未提供' : `实际费用 ${response.usage.actual_cost_usd}` }}</span>
      </div>

      <ol v-if="events.length" class="trace-events" aria-label="Agent 实际执行事件">
        <li v-for="(event, index) in events" :key="event.key" class="trace-event" :class="event.statusCode">
          <span class="trace-event-index" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="trace-event-body">
            <div class="trace-event-title">
              <strong>{{ event.title }}</strong>
              <span class="trace-event-status">{{ event.statusLabel }}</span>
            </div>
            <p v-if="event.parameterSummary">{{ event.parameterSummary }}</p>
            <p v-if="event.resultSummary" class="trace-event-result">
              <CircleCheck v-if="event.statusCode === 'completed' || event.statusCode === 'cached'" :size="14" />
              <MinusCircle v-else-if="event.statusCode === 'failed'" :size="14" />
              <span>{{ event.resultSummary }}</span>
            </p>
          </div>
        </li>
      </ol>
      <p v-else class="trace-empty">本次服务未返回详细轨迹；下方仅展示真实任务状态和回答。</p>

      <section class="trace-answer" aria-label="Agent 回答与证据">
        <div class="trace-answer-heading">
          <h4>回答与原文证据</h4>
          <span v-if="response.answer">{{ response.answer.status === 'answered' ? '回答已生成' : response.answer.status }}</span>
        </div>
        <p v-if="response.answer" class="trace-answer-text">{{ response.answer.answer }}</p>
        <p v-else class="trace-no-answer">未生成回答：{{ stopReasonLabel(response.stop_reason) }}</p>

        <ul v-if="citations.length" class="trace-citations" aria-label="回答引用">
          <li v-for="(evidence, index) in citations" :key="evidence.chunk_id">
            <button type="button" @click="emit('open-evidence', evidence)">
              <span class="citation-number">[{{ index + 1 }}]</span>
              <span class="citation-source">{{ evidence.source.source_path }} · {{ locationLabel(evidence) }}</span>
              <ArrowUpRight :size="15" aria-hidden="true" />
            </button>
            <p>{{ evidence.text.slice(0, 180) }}{{ evidence.text.length > 180 ? '…' : '' }}</p>
          </li>
        </ul>

        <div v-for="artifact in response.artifacts" :key="artifact.kind" class="trace-verdicts">
          <h5>{{ artifact.kind === 'claim_verification' ? '逐条结论核查' : '研究产物' }}</h5>
          <div v-for="verdict in artifact.verdicts ?? []" :key="verdict.claim.statement" class="trace-verdict">
            <span :class="verdict.status">{{ claimStatusLabel(verdict.status) }}</span>
            <p>{{ verdict.claim.statement }}</p>
            <button
              v-if="verdict.evidence[0]"
              type="button"
              class="text-button"
              @click="emit('open-evidence', verdict.evidence[0])"
            >查看支持材料</button>
          </div>
        </div>
      </section>
    </template>

    <p v-else class="trace-empty">尚未运行 Agent。在线执行只会在你点击“运行核查”后提交。</p>
  </section>
</template>
