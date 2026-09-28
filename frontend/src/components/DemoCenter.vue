<script setup lang="ts">
import PanelCollapseButton from './PanelCollapseButton.vue'

withDefaults(defineProps<{
  demoMode?: boolean
  busy?: boolean
  staticDemoOnly?: boolean
  expanded?: boolean
}>(), {
  demoMode: false,
  busy: false,
  staticDemoOnly: false,
  expanded: true,
})

const emit = defineEmits<{
  'load-demo': []
  'toggle-collapse': []
}>()

const stages = [
  { time: '00:00', title: '问题场景', detail: '提出可核查的科研问题', href: '#demo' },
  { time: '00:30', title: '论文筛选', detail: '检索候选与原文依据', href: '#papers' },
  { time: '01:05', title: '信息卡与历史', detail: '字段、版本和证据位置', href: '#card' },
  { time: '01:45', title: 'Agent 工具', detail: '观察实际调用与停止原因', href: '#reproduction' },
  { time: '03:10', title: '证据与结论', detail: '回到原文检查回答', href: '#evidence' },
]
</script>

<template>
  <section id="demo" class="demo-center" :class="{ 'is-collapsed': !expanded }" aria-labelledby="demo-center-title">
    <header class="demo-center-summary">
      <div>
        <p class="demo-eyebrow">ICAN / RESEARCH WALKTHROUGH</p>
        <h2 id="demo-center-title">一篇论文，走完可核查的研究流程</h2>
      </div>
      <div class="demo-center-summary-actions">
        <strong :class="['demo-mode-value', { replay: demoMode }]">
          {{ demoMode ? '预置运行回放 · 只读' : '在线工作台 · 未提交任务' }}
        </strong>
        <PanelCollapseButton
          :expanded="expanded"
          controls="demo-panel-body"
          label="演示中心"
          @toggle="emit('toggle-collapse')"
        />
      </div>
    </header>

    <div id="demo-panel-body" v-show="expanded" class="panel-body">
      <header class="demo-center-header">
        <div class="demo-mode-panel">
          <div class="demo-mode-copy">
            <span class="demo-mode-caption">当前演示模式</span>
            <p v-if="demoMode">本地快照来自已完成的开发运行；浏览不会访问模型、服务或本地存储。</p>
            <p v-else>在线 Agent 仅在你点击“运行核查”后提交；请求完成后展示服务端返回的实际轨迹。</p>
          </div>
          <div class="demo-mode-actions">
            <button class="demo-replay-button" type="button" :disabled="demoMode || busy" @click="emit('load-demo')">
              {{ demoMode ? '只读回放已载入' : busy ? '请等待当前任务结束' : '载入 Swin 只读回放' }}
            </button>
            <a v-if="!staticDemoOnly" href="#reproduction" class="demo-live-link">前往 Agent 输入区 <span aria-hidden="true">↘</span></a>
          </div>
        </div>
      </header>

      <nav class="demo-stage-nav" aria-label="五分钟演示流程">
        <ol>
          <li v-for="(stage, index) in stages" :key="stage.title">
            <a :href="stage.href">
              <span class="demo-stage-index">0{{ index + 1 }}</span>
              <span class="demo-stage-content">
                <span class="demo-stage-time">{{ stage.time }}</span>
                <strong>{{ stage.title }}</strong>
                <small>{{ stage.detail }}</small>
              </span>
              <span v-if="index < stages.length - 1" class="demo-stage-connector" aria-hidden="true" />
            </a>
          </li>
        </ol>
      </nav>
    </div>
  </section>
</template>
