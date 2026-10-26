<template>
  <el-tag :type="map[status]" size="small" effect="light" round>{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { SessionStatus } from '@/types'

const props = defineProps<{ status: SessionStatus }>()

const map: Record<SessionStatus, 'warning' | 'success' | 'info'> = {
  queued: 'warning',
  active: 'success',
  ended: 'info',
}
const labelMap: Record<SessionStatus, string> = {
  queued: '排队中',
  active: '已接入',
  ended: '已结束',
}

const label = computed(() => labelMap[props.status])
</script>
