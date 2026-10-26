import { defineStore } from 'pinia'

import { mockSessions } from '@/mocks'
import { listSessions, updateSessionStatus } from '@/api/operations'
import type { AgentStatus, Session } from '@/types'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [...mockSessions] as Session[],
    activeId: 's-1001' as string | null,
    agentStatus: 'online' as AgentStatus,
  }),
  getters: {
    activeSession: (s): Session | undefined => s.sessions.find((x) => x.id === s.activeId),
    queuedCount: (s) => s.sessions.filter((x) => x.status === 'queued').length,
  },
  actions: {
    async fetch() {
      try {
        const response = await listSessions()
        this.sessions = response.data
        this.activeId = this.sessions[0]?.id ?? null
      } catch {
        // 后端不可用时保留本地会话，便于工作台继续展示。
      }
    },
    select(id: string) {
      this.activeId = id
      const s = this.sessions.find((x) => x.id === id)
      if (s) s.unread = 0
    },
    /** 人工接管：排队中 → 已接入 */
    async takeOver(id: string) {
      const s = this.sessions.find((x) => x.id === id)
      if (s) s.status = 'active'
      await updateSessionStatus(id, 'active').catch(() => undefined)
    },
    async endSession(id: string) {
      const s = this.sessions.find((x) => x.id === id)
      if (s) s.status = 'ended'
      await updateSessionStatus(id, 'ended').catch(() => undefined)
    },
    /** 转交（演示：仅更新更新时间） */
    async transfer(id: string) {
      const s = this.sessions.find((x) => x.id === id)
      if (s) s.updatedAt = Date.now()
      await updateSessionStatus(id, 'queued').catch(() => undefined)
    },
    setAgentStatus(status: AgentStatus) {
      this.agentStatus = status
    },
    /** 客户转人工：新增一条排队会话 */
    addTransferSession() {
      this.sessions.unshift({
        id: `s-${Date.now()}`,
        customerId: 'c-transfer',
        customerName: '转人工客户',
        avatar: '客',
        status: 'queued',
        lastMessage: '请求人工客服',
        updatedAt: Date.now(),
        unread: 1,
        tags: ['转人工'],
      })
    },
  },
})
