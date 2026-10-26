<template>
  <div class="loading-state">
    <el-icon class="loading-state__icon is-loading" :size="size"><Loading /></el-icon>
    <span v-if="text" class="loading-state__text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

withDefaults(defineProps<{ text?: string; size?: number }>(), { size: 20 })
</script>

<style scoped lang="scss">
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sl-space-sm);
  padding: var(--sl-space-xl);
  color: var(--sl-text-secondary);
}
.loading-state__icon {
  color: var(--sl-primary);
}
.loading-state__text {
  font-size: var(--sl-font-size-sm);
}
</style>
