<template>
  <div class="dashboard">
    <div class="dashboard__stats">
      <div v-for="s in stats" :key="s.label" class="stat-card">
        <div class="stat-card__icon" :style="{ color: s.color, background: s.bg }">
          <el-icon :size="22"><component :is="s.icon" /></el-icon>
        </div>
        <div>
          <div class="stat-card__value">{{ s.value }}</div>
          <div class="stat-card__label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <el-card class="dashboard__chart-card" shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span>会话趋势</span>
          <el-tag size="small" type="info">近 24 小时</el-tag>
        </div>
      </template>
      <BaseChart :option="chartOption" height="360px" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ChatDotRound, TrendCharts, Timer, Warning } from '@element-plus/icons-vue'
import type { EChartsOption } from 'echarts'
import { computed, onMounted } from 'vue'

import BaseChart from '@/components/common/BaseChart.vue'
import { useAppStore } from '@/stores/app'
import { useDashboardStore } from '@/stores/dashboard'

const appStore = useAppStore()
const dashboard = useDashboardStore()

const stats = computed(() => [
  {
    label: '会话量',
    value: dashboard.metrics.sessions.toLocaleString(),
    icon: ChatDotRound,
    color: '#4f6ef2',
    bg: 'rgba(79,110,242,.12)',
  },
  {
    label: '成功率',
    value: `${(dashboard.metrics.successRate * 100).toFixed(1)}%`,
    icon: TrendCharts,
    color: '#16a34a',
    bg: 'rgba(22,163,74,.12)',
  },
  {
    label: '首字延迟',
    value: `${dashboard.metrics.firstTokenLatency}ms`,
    icon: Timer,
    color: '#d97706',
    bg: 'rgba(217,119,6,.12)',
  },
  {
    label: '降级次数',
    value: dashboard.metrics.degradations,
    icon: Warning,
    color: '#dc2626',
    bg: 'rgba(220,38,38,.12)',
  },
])

const chartOption = computed<EChartsOption>(() => {
  const dark = appStore.isDark
  const axisColor = dark ? '#94a3b8' : '#64748b'
  const gridColor = dark ? '#2a333f' : '#e2e8f0'
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['会话量', '成功率'], top: 0 },
    grid: { left: 48, right: 48, top: 48, bottom: 28 },
    xAxis: {
      type: 'category',
      data: dashboard.metrics.trend.map((t) => t.time),
      boundaryGap: true,
      axisLine: { lineStyle: { color: axisColor } },
      axisLabel: { color: axisColor },
    },
    yAxis: [
      {
        type: 'value',
        name: '会话量',
        splitLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: axisColor },
      },
      {
        type: 'value',
        name: '成功率',
        max: 1,
        axisLabel: {
          color: axisColor,
          formatter: (v: number) => `${Math.round(v * 100)}%`,
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '会话量',
        type: 'bar',
        data: dashboard.metrics.trend.map((t) => t.sessions),
        itemStyle: { color: '#4f6ef2', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 28,
      },
      {
        name: '成功率',
        type: 'line',
        yAxisIndex: 1,
        data: dashboard.metrics.trend.map((t) => t.successRate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#16a34a', width: 2 },
        itemStyle: { color: '#16a34a' },
      },
    ],
  }
})

onMounted(() => dashboard.fetch())
</script>

<style scoped lang="scss">
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--sl-space-lg);
}
.dashboard__stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sl-space-md);
}
.stat-card {
  display: flex;
  align-items: center;
  gap: var(--sl-space-md);
  padding: var(--sl-space-lg);
  background: var(--sl-bg-surface);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-lg);
}
.stat-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--sl-radius-md);
  flex-shrink: 0;
}
.stat-card__value {
  font-size: var(--sl-font-size-2xl);
  font-weight: var(--sl-font-weight-semibold);
  line-height: 1.2;
}
.stat-card__label {
  font-size: var(--sl-font-size-sm);
  color: var(--sl-text-secondary);
}

@media (max-width: 1200px) {
  .dashboard__stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
