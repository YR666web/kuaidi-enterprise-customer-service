<template>
  <div class="empty-state">
    <el-icon :size="46" class="empty-state__icon"><Box /></el-icon>
    <div class="empty-state__title">{{ title }}</div>
    <div v-if="description" class="empty-state__desc">{{ description }}</div>
    <div v-if="$slots.default" class="empty-state__action">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Box } from '@element-plus/icons-vue'

withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: '暂无数据',
  description: '',
})
</script>

<style scoped lang="scss">
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sl-space-xs);
  padding: var(--sl-space-2xl);
  color: var(--sl-text-secondary);
}
.empty-state__icon {
  color: var(--sl-text-placeholder);
  margin-bottom: var(--sl-space-sm);
}
.empty-state__title {
  font-size: var(--sl-font-size-md);
  font-weight: var(--sl-font-weight-medium);
  color: var(--sl-text-regular);
}
.empty-state__desc {
  font-size: var(--sl-font-size-sm);
  max-width: 320px;
  text-align: center;
}
.empty-state__action {
  margin-top: var(--sl-space-md);
}
</style>
