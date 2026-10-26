<template>
  <div class="chat">
    <header class="chat__header">
      <div class="chat__brand">
        <span class="chat__logo">栈</span>
        <div>
          <div class="chat__title">快递企业智能客服</div>
          <div class="chat__status">
            <span class="chat__dot" :class="{ 'chat__dot--on': chat.connected }"></span>
            {{ chat.connected ? '在线 · 实时' : '连接中…' }}
          </div>
        </div>
      </div>
      <div class="chat__actions">
        <el-button link type="primary" @click="onTransfer">转人工</el-button>
        <el-dropdown @command="navTo">
          <el-button link>
            切换端
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/chat">用户对话端</el-dropdown-item>
              <el-dropdown-item command="/workbench">客服工作台</el-dropdown-item>
              <el-dropdown-item command="/admin">运营后台</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-icon class="chat__theme" @click="appStore.toggleDark()">
          <Moon v-if="!appStore.isDark" />
          <Sunny v-else />
        </el-icon>
      </div>
    </header>

    <main ref="scrollEl" class="chat__messages">
      <EmptyState
        v-if="!chat.messages.length"
        title="您好，我是快递企业智能客服"
        description="请输入您的问题，或点击下方快捷按钮快速开始"
      />
      <MessageBubble
        v-for="m in chat.messages"
        :key="m.id"
        :message="m"
        @locate="openCitation"
      />
      <TypingIndicator v-if="typing" />
    </main>

    <footer class="chat__composer">
      <div class="chat__quick">
        <span class="chat__quick-label">快捷提问：</span>
        <el-tag
          v-for="q in quickReplies"
          :key="q"
          class="chat__quick-tag"
          effect="plain"
          @click="send(q)"
        >
          {{ q }}
        </el-tag>
      </div>
      <div class="chat__input">
        <el-input
          v-model="input"
          size="large"
          placeholder="请输入您的问题，Enter 发送…"
          @keyup.enter="send()"
        />
        <el-button type="primary" size="large" :loading="chat.streaming" @click="send()">
          发送
        </el-button>
      </div>
    </footer>

    <el-dialog v-model="citationVisible" title="引用来源" width="520px">
      <div class="citation-detail">
        <div class="citation-detail__doc">
          <el-icon><Document /></el-icon>
          {{ currentCitation?.docId }}
          <el-tag v-if="currentCitation?.page" size="small" type="info">
            第 {{ currentCitation.page }} 页
          </el-tag>
        </div>
        <p class="citation-detail__snippet">{{ currentCitation?.snippet }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown, Document, Moon, Sunny } from '@element-plus/icons-vue'
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import MessageBubble from '@/components/chat/MessageBubble.vue'
import TypingIndicator from '@/components/chat/TypingIndicator.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { mockQuickReplies } from '@/mocks'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import type { Citation } from '@/types'

const appStore = useAppStore()
const chat = useChatStore()
const router = useRouter()

const input = ref('')
const scrollEl = ref<HTMLElement>()
const citationVisible = ref(false)
const currentCitation = ref<Citation | null>(null)
const quickReplies = mockQuickReplies

const typing = computed(() => chat.thinking)

async function send(text?: string) {
  const value = (text ?? input.value).trim()
  if (!value) return
  input.value = ''
  await chat.send(value)
  await nextTick()
  scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
}

async function onTransfer() {
  await chat.transferToHuman()
}

function openCitation(c: Citation) {
  currentCitation.value = c
  citationVisible.value = true
}

function navTo(path: string) {
  router.push(path)
}

onMounted(() => {
  chat.connect()
})
</script>

<style scoped lang="scss">
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 900px;
  margin: 0 auto;
}
.chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sl-space-md) var(--sl-space-lg);
  background: var(--sl-bg-surface);
  border-bottom: 1px solid var(--sl-border);
}
.chat__brand {
  display: flex;
  align-items: center;
  gap: var(--sl-space-sm);
}
.chat__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--sl-radius-lg);
  background: var(--sl-primary);
  color: #fff;
  font-size: var(--sl-font-size-lg);
  font-weight: var(--sl-font-weight-semibold);
}
.chat__title {
  font-size: var(--sl-font-size-lg);
  font-weight: var(--sl-font-weight-semibold);
}
.chat__status {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-secondary);
}
.chat__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sl-text-placeholder);

  &--on {
    background: var(--sl-success);
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
  }
}
.chat__actions {
  display: flex;
  align-items: center;
  gap: var(--sl-space-md);
}
.chat__theme {
  font-size: 18px;
  color: var(--sl-text-secondary);
  cursor: pointer;

  &:hover {
    color: var(--sl-primary);
  }
}
.chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--sl-space-lg);
}
.chat__composer {
  padding: var(--sl-space-md) var(--sl-space-lg);
  background: var(--sl-bg-surface);
  border-top: 1px solid var(--sl-border);
}
.chat__quick {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
  margin-bottom: var(--sl-space-sm);
  flex-wrap: wrap;
}
.chat__quick-label {
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-secondary);
}
.chat__quick-tag {
  cursor: pointer;

  &:hover {
    color: var(--sl-primary);
    border-color: var(--sl-primary);
  }
}
.chat__input {
  display: flex;
  gap: var(--sl-space-sm);
}
.citation-detail__doc {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
  font-weight: var(--sl-font-weight-medium);
  margin-bottom: var(--sl-space-md);
}
.citation-detail__snippet {
  margin: 0;
  padding: var(--sl-space-md);
  background: var(--sl-bg-subtle);
  border-radius: var(--sl-radius-md);
  line-height: var(--sl-line-height);
  color: var(--sl-text-regular);
}
</style>
