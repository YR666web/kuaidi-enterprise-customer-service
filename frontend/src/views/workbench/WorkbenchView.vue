<template>
  <div class="workbench">
    <header class="workbench__header">
      <div class="workbench__brand">
        <span class="workbench__logo">栈</span>
        <span class="workbench__title">客服工作台</span>
      </div>
      <div class="workbench__actions">
        <div class="workbench__agent-status">
          <span class="workbench__status-label">坐席状态</span>
          <el-radio-group v-model="sessionStore.agentStatus" size="small">
            <el-radio-button value="online">在线</el-radio-button>
            <el-radio-button value="busy">小休</el-radio-button>
            <el-radio-button value="offline">离线</el-radio-button>
          </el-radio-group>
        </div>
        <el-dropdown @command="navTo">
          <el-button text>
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
        <el-icon class="workbench__theme" @click="appStore.toggleDark()">
          <Moon v-if="!appStore.isDark" />
          <Sunny v-else />
        </el-icon>
      </div>
    </header>

    <div class="workbench__body">
      <!-- 会话列表 -->
      <aside class="workbench__sessions">
        <div class="workbench__sessions-head">
          <el-input v-model="keyword" size="small" placeholder="搜索会话" :prefix-icon="Search" clearable />
        </div>
        <div class="workbench__sessions-list">
          <div
            v-for="s in filteredSessions"
            :key="s.id"
            class="session-item"
            :class="{ 'session-item--active': s.id === sessionStore.activeId }"
            @click="sessionStore.select(s.id)"
          >
            <div class="session-item__top">
              <el-avatar :size="34">{{ s.avatar }}</el-avatar>
              <div class="flex-1">
                <div class="session-item__name">
                  {{ s.customerName }}
                  <el-badge v-if="s.unread" :value="s.unread" class="session-item__badge" />
                </div>
                <div class="session-item__msg truncate">{{ s.lastMessage }}</div>
              </div>
            </div>
            <div class="session-item__bottom">
              <StatusTag :status="s.status" />
              <span class="session-item__time">{{ timeAgo(s.updatedAt) }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 对话区 -->
      <main class="workbench__conversation">
        <div v-if="active" class="workbench__conv-head">
          <div>
            <div class="workbench__conv-name">{{ active.customerName }}</div>
            <div class="workbench__conv-tags">
              <el-tag v-for="t in active.tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
            </div>
          </div>
          <div class="workbench__conv-actions">
            <el-button v-if="active.status === 'queued'" type="primary" size="small" @click="onTakeOver">
              接管
            </el-button>
            <el-button v-if="active.status === 'active'" size="small" @click="onTransfer">
              <el-icon><Switch /></el-icon>
              转交
            </el-button>
            <el-button v-if="active.status === 'active'" type="danger" plain size="small" @click="onEnd">
              结束会话
            </el-button>
          </div>
        </div>

        <div class="workbench__messages">
          <template v-if="active">
            <div
              v-for="m in chatStore.messages"
              :key="m.id"
              class="msg"
              :class="m.role === 'user' ? 'msg--left' : 'msg--right'"
            >
              <div class="msg__bubble">{{ m.content }}</div>
            </div>
            <TypingIndicator v-if="typing" />
          </template>
          <EmptyState v-else title="选择左侧会话开始接待" description="会话列表展示待处理与进行中的客户" />
        </div>

        <div class="workbench__composer">
          <el-input
            v-model="reply"
            size="large"
            placeholder="输入回复内容，Enter 发送…"
            :disabled="!active || active.status === 'ended'"
            @keyup.enter="sendReply"
          />
          <el-button type="primary" size="large" :disabled="!active" @click="sendReply">
            发送
          </el-button>
        </div>
      </main>

      <!-- 用户信息侧栏 -->
      <aside class="workbench__profile">
        <template v-if="active">
          <div class="workbench__profile-head">
            <el-avatar :size="56">{{ active.avatar }}</el-avatar>
            <div class="workbench__profile-name">{{ active.customerName }}</div>
            <div class="workbench__profile-id">ID: {{ active.customerId }}</div>
          </div>
          <el-divider />
          <div class="workbench__profile-block">
            <div class="workbench__profile-label">客户标签</div>
            <div class="workbench__profile-tags">
              <el-tag v-for="t in active.tags" :key="t" size="small">{{ t }}</el-tag>
              <span v-if="!active.tags.length" class="text-secondary text-sm">无</span>
            </div>
          </div>
          <div class="workbench__profile-block">
            <div class="workbench__profile-label">最近订单</div>
            <div class="workbench__order">订单 #20260812001 · 已发货</div>
            <div class="workbench__order">订单 #20260819007 · 待付款</div>
          </div>
        </template>
        <EmptyState v-else title="未选择会话" />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown, Moon, Search, Sunny, Switch } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import TypingIndicator from '@/components/chat/TypingIndicator.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

const appStore = useAppStore()
const chatStore = useChatStore()
const sessionStore = useSessionStore()
const router = useRouter()

const keyword = ref('')
const reply = ref('')
const typing = ref(false)

onMounted(() => sessionStore.fetch())

const active = computed(() => sessionStore.activeSession)
const filteredSessions = computed(() => {
  if (!keyword.value) return sessionStore.sessions
  return sessionStore.sessions.filter((s) => s.customerName.includes(keyword.value))
})

function onTakeOver() {
  if (sessionStore.activeId) {
    sessionStore.takeOver(sessionStore.activeId)
    ElMessage.success('已接管会话')
  }
}
function onEnd() {
  if (sessionStore.activeId) {
    sessionStore.endSession(sessionStore.activeId)
    ElMessage.success('会话已结束')
  }
}
function onTransfer() {
  if (sessionStore.activeId) {
    sessionStore.transfer(sessionStore.activeId)
    ElMessage.success('已转交会话')
  }
}
function sendReply() {
  const text = reply.value.trim()
  if (!text) return
  chatStore.messages.push({
    id: `m-${Date.now()}`,
    role: 'assistant',
    content: text,
    createdAt: Date.now(),
  })
  reply.value = ''
}
function timeAgo(ts: number) {
  const m = Math.floor((Date.now() - ts) / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  return `${Math.floor(m / 60)} 小时前`
}
function navTo(path: string) {
  router.push(path)
}
</script>

<style scoped lang="scss">
.workbench {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.workbench__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 var(--sl-space-lg);
  background: var(--sl-bg-surface);
  border-bottom: 1px solid var(--sl-border);
}
.workbench__brand {
  display: flex;
  align-items: center;
  gap: var(--sl-space-sm);
}
.workbench__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--sl-radius-md);
  background: var(--sl-primary);
  color: #fff;
  font-weight: var(--sl-font-weight-semibold);
}
.workbench__title {
  font-weight: var(--sl-font-weight-semibold);
  font-size: var(--sl-font-size-lg);
}
.workbench__actions {
  display: flex;
  align-items: center;
  gap: var(--sl-space-md);
}
.workbench__agent-status {
  display: flex;
  align-items: center;
  gap: var(--sl-space-sm);
}
.workbench__status-label {
  font-size: var(--sl-font-size-sm);
  color: var(--sl-text-secondary);
}
.workbench__theme {
  font-size: 18px;
  color: var(--sl-text-secondary);
  cursor: pointer;

  &:hover {
    color: var(--sl-primary);
  }
}
.workbench__role {
  cursor: pointer;
}
.workbench__body {
  display: flex;
  flex: 1;
  min-height: 0;
}
.workbench__sessions {
  width: 280px;
  border-right: 1px solid var(--sl-border);
  background: var(--sl-bg-surface);
  display: flex;
  flex-direction: column;
}
.workbench__sessions-head {
  padding: var(--sl-space-md);
  border-bottom: 1px solid var(--sl-border-light);
}
.workbench__sessions-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  padding: var(--sl-space-md);
  border-bottom: 1px solid var(--sl-border-light);
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: var(--sl-bg-subtle);
  }
  &--active {
    background: var(--sl-primary-soft);
    border-left: 3px solid var(--sl-primary);
  }
}
.session-item__top {
  display: flex;
  gap: var(--sl-space-sm);
  align-items: center;
}
.session-item__name {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
  font-weight: var(--sl-font-weight-medium);
}
.session-item__badge {
  transform: scale(0.8);
}
.session-item__msg {
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-secondary);
  margin-top: 2px;
}
.session-item__bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--sl-space-sm);
}
.session-item__time {
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-placeholder);
}
.workbench__conversation {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.workbench__conv-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sl-space-md) var(--sl-space-lg);
  border-bottom: 1px solid var(--sl-border);
  background: var(--sl-bg-surface);
}
.workbench__conv-name {
  font-weight: var(--sl-font-weight-semibold);
}
.workbench__conv-tags {
  display: flex;
  gap: var(--sl-space-xs);
  margin-top: var(--sl-space-xs);
}
.workbench__conv-actions {
  display: flex;
  gap: var(--sl-space-sm);
}
.workbench__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--sl-space-lg);
  display: flex;
  flex-direction: column;
}
.msg {
  display: flex;
  margin-bottom: var(--sl-space-md);

  &--left {
    justify-content: flex-start;
    .msg__bubble {
      background: var(--sl-bg-surface);
      border: 1px solid var(--sl-border);
    }
  }
  &--right {
    justify-content: flex-end;
    .msg__bubble {
      background: var(--sl-primary);
      color: #fff;
    }
  }
}
.msg__bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: var(--sl-radius-lg);
  line-height: var(--sl-line-height);
}
.workbench__composer {
  display: flex;
  gap: var(--sl-space-sm);
  padding: var(--sl-space-md) var(--sl-space-lg);
  border-top: 1px solid var(--sl-border);
  background: var(--sl-bg-surface);
}
.workbench__profile {
  width: 260px;
  border-left: 1px solid var(--sl-border);
  background: var(--sl-bg-surface);
  padding: var(--sl-space-md);
  overflow-y: auto;
}
.workbench__profile-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sl-space-xs);
}
.workbench__profile-name {
  font-weight: var(--sl-font-weight-semibold);
}
.workbench__profile-id {
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-secondary);
}
.workbench__profile-block {
  margin-bottom: var(--sl-space-md);
}
.workbench__profile-label {
  font-size: var(--sl-font-size-xs);
  color: var(--sl-text-secondary);
  margin-bottom: var(--sl-space-xs);
}
.workbench__profile-tags {
  display: flex;
  gap: var(--sl-space-xs);
  flex-wrap: wrap;
}
.workbench__order {
  font-size: var(--sl-font-size-sm);
  color: var(--sl-text-regular);
  padding: var(--sl-space-xs) 0;
  border-bottom: 1px dashed var(--sl-border-light);
}
</style>
