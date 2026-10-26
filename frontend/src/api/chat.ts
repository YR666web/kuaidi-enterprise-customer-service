import http from './http'

export interface ChatRequest {
  message: string
  session_id: string
  user_id?: string
}

export interface ChatResponse {
  session_id: string
  message: string
  intent?: string
  citations: string[]
  degradation_path: string[]
}

export interface HandoffRequest {
  session_id: string
  reason?: string
  transcript: Array<{ role: 'user' | 'assistant'; content: string }>
}

export function sendChat(request: ChatRequest) {
  return http.post<ChatResponse>('/chat', request)
}

export function requestHandoff(request: HandoffRequest) {
  return http.post('/chat/handoff', request)
}

export async function streamChat(
  request: ChatRequest,
  onDelta: (text: string) => void,
  onDone?: (payload: Record<string, unknown>) => void,
) {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  // Token 只能来自显式登录，不在 Vite 构建物中嵌入管理员凭证。
  const token = localStorage.getItem('sl-token')
  const response = await fetch(`${baseURL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  })
  if (!response.ok || !response.body) {
    throw new Error(`聊天请求失败（${response.status}）`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const event of events) {
      const line = event.split('\n').find((item) => item.startsWith('data: '))
      if (!line) continue
      const payload = JSON.parse(line.slice(6)) as Record<string, unknown>
      if (typeof payload.delta === 'string') onDelta(payload.delta)
      if (payload.done) onDone?.(payload)
    }
    if (done) break
  }
}
