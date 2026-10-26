<template>
  <div class="bubble" :class="`bubble--${message.role}`">
    <div class="bubble__body">
      <div class="bubble__text">
        {{ message.content }}
        <span v-if="message.streaming" class="bubble__cursor">▌</span>
      </div>

      <div v-if="message.citations?.length" class="bubble__citations">
        <div
          v-for="(c, i) in message.citations"
          :key="i"
          class="citation"
          @click="$emit('locate', c)"
        >
          <el-icon :size="12"><Document /></el-icon>
          <span class="citation__doc">{{ c.docId }}</span>
          <span class="citation__page">{{ c.page ? `P${c.page}` : '片段' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'

import type { ChatMessage, Citation } from '@/types'

defineProps<{ message: ChatMessage }>()
defineEmits<{ (e: 'locate', citation: Citation): void }>()
</script>

<style scoped lang="scss">
.bubble {
  display: flex;
  margin-bottom: var(--sl-space-md);

  &--user {
    justify-content: flex-end;

    .bubble__body {
      background: var(--sl-primary);
      color: #fff;
      border-bottom-right-radius: var(--sl-radius-sm);
    }
  }

  &--assistant {
    justify-content: flex-start;

    .bubble__body {
      background: var(--sl-bg-elevated);
      color: var(--sl-text-primary);
      border: 1px solid var(--sl-border);
      border-bottom-left-radius: var(--sl-radius-sm);
    }
  }
}

.bubble__body {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: var(--sl-radius-lg);
  line-height: var(--sl-line-height);
  font-size: var(--sl-font-size-md);
  word-break: break-word;
}

.bubble__cursor {
  animation: blink 1s step-end infinite;
  color: var(--sl-primary);
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.bubble__citations {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sl-space-xs);
  margin-top: var(--sl-space-sm);
  padding-top: var(--sl-space-sm);
  border-top: 1px solid var(--sl-border-light);
}

.citation {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  font-size: var(--sl-font-size-xs);
  color: var(--sl-primary);
  background: var(--sl-primary-soft);
  border-radius: var(--sl-radius-sm);
  cursor: pointer;
  transition: opacity 0.15s;

  &:hover {
    opacity: 0.8;
  }
}
.citation__page {
  color: var(--sl-text-secondary);
}
</style>
