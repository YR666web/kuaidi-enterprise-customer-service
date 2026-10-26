// 共享类型定义

export type Role = 'agent' | 'operator' | 'admin'

export interface UserInfo {
  id: string
  name: string
  role: Role
  tenantId: string
  avatar?: string
}

export type Permission = string

// 角色 → 权限
export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  agent: ['chat:write', 'knowledge:read'],
  operator: [
    'chat:write',
    'knowledge:read',
    'knowledge:write',
    'flow:config',
    'data:export',
  ],
  admin: ['*'],
}

export interface Citation {
  docId: string
  snippet: string
  page?: number
  index: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  streaming?: boolean
  createdAt: number
}

export type SessionStatus = 'queued' | 'active' | 'ended'

export interface Session {
  id: string
  customerId: string
  customerName: string
  avatar: string
  status: SessionStatus
  lastMessage: string
  updatedAt: number
  unread: number
  tags: string[]
}

export interface KnowledgeDoc {
  id: string
  name: string
  type: 'pdf' | 'markdown' | 'text'
  size: number
  chunks: number
  status: 'processing' | 'ready' | 'failed'
  uploadedAt: number
}

export interface FlowConfig {
  id: string
  name: string
  description: string
  steps: number
  updatedAt: number
}

export interface TrendPoint {
  time: string
  sessions: number
  successRate: number
}

export interface DashboardMetrics {
  sessions: number
  successRate: number
  firstTokenLatency: number
  degradations: number
  trend: TrendPoint[]
}

export type AgentStatus = 'online' | 'busy' | 'offline'
