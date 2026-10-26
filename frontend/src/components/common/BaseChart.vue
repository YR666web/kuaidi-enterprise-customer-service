<template>
  <div ref="chartEl" class="base-chart" :style="{ height }"></div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ option: echarts.EChartsOption; height?: string }>(), {
  height: '300px',
})

const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(props.option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.base-chart {
  width: 100%;
}
</style>
