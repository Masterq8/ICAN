<script setup lang="ts">
import { ChevronDown, ChevronUp } from '@lucide/vue'

defineProps<{
  expanded: boolean
  controls: string
  label: string
}>()

defineEmits<{
  toggle: []
}>()
</script>

<template>
  <button
    type="button"
    class="text-button panel-collapse-button"
    :aria-label="`${expanded ? '收起' : '展开'}${label}`"
    :aria-expanded="expanded"
    :aria-controls="controls"
    @click="$emit('toggle')"
  >
    <ChevronUp v-if="expanded" :size="17" aria-hidden="true" />
    <ChevronDown v-else :size="17" aria-hidden="true" />
    {{ expanded ? '收起' : '展开' }}
  </button>
</template>
