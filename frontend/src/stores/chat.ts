import { defineStore } from 'pinia'

import { requestHandoff, streamChat } from '@/api/chat'
import type { ChatMessage, Citation } from '@/types'

let seq = 0
const sessionId = `s-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
function uid() {
  seq += 1
  return `m-${Date.now()}-${seq}`
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [] as ChatMessage[],
    streaming: false,
    thinking: false,
    connected: false,
    transferred: false,
  }),
  getters: {
    lastMessage: (s) => s.messages[s.messages.length - 1],
  },
  actions: {
    connect() {
      this.connected = true
    },
    disconnect() {
      this.connected = false
    },
    pushUser(text: string) {
      this.messages.push({ id: uid(), role: 'user', content: text, createdAt: Date.now() })
    },
    /** 发送消息并模拟流式回复 */
    async send(text: string) {
      this.pushUser(text)
      if (text.includes('转人工') || text.includes('人工客服')) {
        this.transferToHuman()
        return
      }
      this.thinking = true
      this.messages.push({
        id: uid(),
        role: 'assistant',
        content: '',
        streaming: true,
        createdAt: Date.now(),
      })
      this.thinking = false
      this.streaming = true
      const target = this.messages[this.messages.length - 1]
      try {
        await streamChat(
          { message: text, session_id: sessionId },
          (delta) => {
            target.content += delta
          },
        )
      } catch (error) {
        target.content = error instanceof Error ? error.message : '服务暂时不可用，请稍后重试。'
      } finally {
        target.streaming = false
        this.streaming = false
      }
    },
    async transferToHuman() {
      this.transferred = true
      this.messages.push({
        id: uid(),
        role: 'assistant',
        content: '已为您转接人工客服，坐席将尽快接入，请稍候…',
        createdAt: Date.now(),
      })
      try {
        await requestHandoff({
          session_id: sessionId,
          transcript: this.messages
            .filter((message) => message.role === 'user' || message.role === 'assistant')
            .map((message) => ({ role: message.role, content: message.content })),
        })
      } catch {
        this.messages.push({
          id: uid(), role: 'assistant',
          content: '人工排队请求暂未提交成功，请稍后重试。', createdAt: Date.now(),
        })
      }
    },
    clear() {
      this.messages = []
    },
  },
})
