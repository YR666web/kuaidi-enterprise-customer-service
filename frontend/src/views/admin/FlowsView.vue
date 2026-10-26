<template>
  <div class="flows">
    <div class="flex items-center justify-between">
      <div>
        <div class="flows__title">流程配置</div>
        <div class="text-secondary text-sm">声明式多轮业务流程，YAML 定义，新增流程不改代码</div>
      </div>
      <el-tag type="info">共 {{ flows.length }} 个流程</el-tag>
    </div>

    <div class="flows__grid">
      <el-card v-for="f in flows" :key="f.id" shadow="never" class="flow-card">
        <div class="flow-card__head">
          <el-icon :size="20" class="flow-card__icon"><SetUp /></el-icon>
          <span class="flow-card__name">{{ f.name }}</span>
          <el-tag size="small" effect="plain">{{ f.id }}</el-tag>
        </div>
        <p class="flow-card__desc">{{ f.description }}</p>
        <div class="flow-card__meta">
          <span>{{ f.steps }} 个步骤</span>
          <span>更新于 {{ formatTime(f.updatedAt) }}</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { SetUp } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import { listFlows } from '@/api/operations'
import { mockFlows } from '@/mocks'
import type { FlowConfig } from '@/types'

const flows = ref<FlowConfig[]>([...mockFlows])

onMounted(async () => {
  try {
    flows.value = (await listFlows()).data
  } catch {
    // 保留演示数据，避免后端暂不可用时页面空白。
  }
})

function formatTime(ts: number) {
  return new Date(ts).toLocaleDateString('zh-CN')
}
</script>

<style scoped lang="scss">
.flows {
  display: flex;
  flex-direction: column;
  gap: var(--sl-space-lg);
}
.flows__title {
  font-size: var(--sl-font-size-lg);
  font-weight: var(--sl-font-weight-semibold);
}
.flows__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--sl-space-md);
}
.flow-card__head {
  display: flex;
  align-items: center;
  gap: var(--sl-space-sm);
  margin-bottom: var(--sl-space-sm);
}
.flow-card__icon {
  color: var(--sl-primary);
}
.flow-card__name {
  font-weight: var(--sl-font-weight-semibold);
  font-size: var(--sl-font-size-md);
}
.flow-card__desc {
  margin: 0 0 var(--sl-space-md);
  color: var(--sl-text-secondary);
  font-size: var(--sl-font-size-sm);
  line-height: var(--sl-line-height);
  min-height: 42px;
}
.flow-card__meta {
  display: flex;
  justify-content: space-between;
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-placeholder);
}
</style>
