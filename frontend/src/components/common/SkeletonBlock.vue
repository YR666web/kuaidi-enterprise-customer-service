<template>
  <el-skeleton :rows="rows" :animated="animated" :loading="loading">
    <slot />
  </el-skeleton>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ rows?: number; loading?: boolean; animated?: boolean }>(), {
  rows: 4,
  loading: true,
  animated: true,
})
</script>
