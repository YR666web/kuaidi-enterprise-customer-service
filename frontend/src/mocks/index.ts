// 演示用 Mock 数据（后端 API 未接入前使用，结构对齐真实接口）

import type {
  Citation,
  ChatMessage,
  DashboardMetrics,
  FlowConfig,
  KnowledgeDoc,
  Session,
} from '@/types'

export const mockSessions: Session[] = [
  {
    id: 's-1001',
    customerId: 'c-1',
    customerName: '张女士',
    avatar: '张',
    status: 'active',
    lastMessage: '我的快递什么时候能到？',
    updatedAt: Date.now() - 1000 * 60 * 2,
    unread: 2,
    tags: ['VIP', '售后'],
  },
  {
    id: 's-1002',
    customerId: 'c-2',
    customerName: '李先生',
    avatar: '李',
    status: 'queued',
    lastMessage: '想咨询退货政策',
    updatedAt: Date.now() - 1000 * 60 * 8,
    unread: 0,
    tags: ['新客'],
  },
  {
    id: 's-1003',
    customerId: 'c-3',
    customerName: '王先生',
    avatar: '王',
    status: 'active',
    lastMessage: '地址填错了怎么改',
    updatedAt: Date.now() - 1000 * 60 * 15,
    unread: 1,
    tags: [],
  },
  {
    id: 's-1004',
    customerId: 'c-4',
    customerName: '赵女士',
    avatar: '赵',
    status: 'ended',
    lastMessage: '好的，谢谢',
    updatedAt: Date.now() - 1000 * 60 * 60,
    unread: 0,
    tags: ['已解决'],
  },
]

export const mockMessages: Record<string, ChatMessage[]> = {
  's-1001': [
    {
      id: 'm-1',
      role: 'user',
      content: '我下单的快递什么时候能到？',
      createdAt: Date.now() - 1000 * 60 * 10,
    },
    {
      id: 'm-2',
      role: 'assistant',
      content:
        '根据您的订单，快递预计 3 天内送达。当前物流状态为「已揽收」，您可点击查看最新轨迹。',
      citations: [
        { docId: 'd-1', snippet: '顺丰标准件：1-3 个工作日送达，偏远地区 3-5 个工作日。', index: 0 },
        { docId: 'd-2', snippet: '物流查询：进入订单详情点击「查看物流」可实时追踪。', page: 2, index: 1 },
      ],
      createdAt: Date.now() - 1000 * 60 * 9,
    },
    {
      id: 'm-3',
      role: 'user',
      content: '能加急吗？',
      createdAt: Date.now() - 1000 * 60 * 3,
    },
    {
      id: 'm-4',
      role: 'assistant',
      content: '可以的，加急服务可优先出库，通常可提前 1 天送达。需要我帮您办理加急吗？',
      createdAt: Date.now() - 1000 * 60 * 2,
    },
  ],
}

export const mockKnowledgeDocs: KnowledgeDoc[] = [
  {
    id: 'k-1',
    name: '退换货政策.md',
    type: 'markdown',
    size: 12_480,
    chunks: 18,
    status: 'ready',
    uploadedAt: Date.now() - 1000 * 60 * 60 * 24 * 3,
  },
  {
    id: 'k-2',
    name: '物流时效说明.pdf',
    type: 'pdf',
    size: 842_116,
    chunks: 42,
    status: 'ready',
    uploadedAt: Date.now() - 1000 * 60 * 60 * 24 * 2,
  },
  {
    id: 'k-3',
    name: '售后常见问题.txt',
    type: 'text',
    size: 3_204,
    chunks: 9,
    status: 'processing',
    uploadedAt: Date.now() - 1000 * 60 * 30,
  },
  {
    id: 'k-4',
    name: '大促活动规则.md',
    type: 'markdown',
    size: 20_480,
    chunks: 0,
    status: 'failed',
    uploadedAt: Date.now() - 1000 * 60 * 60 * 5,
  },
]

export const mockFlows: FlowConfig[] = [
  {
    id: 'modify_address',
    name: '修改收货地址',
    description: '收集姓名 / 手机号 / 收货地址，校验后提交。',
    steps: 5,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 5,
  },
  {
    id: 'return_goods',
    name: '退货',
    description: '收集退货原因与商品类型，按生鲜/普通分支处理。',
    steps: 7,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 3,
  },
  {
    id: 'query_logistics',
    name: '查询物流',
    description: '收集快递单号并查询最新物流状态。',
    steps: 2,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24,
  },
]

export const mockDashboard: DashboardMetrics = {
  sessions: 1284,
  successRate: 0.972,
  firstTokenLatency: 860,
  degradations: 43,
  trend: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'].map((time, i) => ({
    time,
    sessions: [80, 42, 96, 210, 320, 268, 150][i],
    successRate: [0.94, 0.91, 0.96, 0.98, 0.97, 0.99, 0.95][i],
  })),
}

export const mockQuickReplies = ['查快递', '退货', '修改地址', '人工客服']

export const mockCitationSnippets: Record<string, Citation[]> = {
  'd-1': [
    {
      docId: '退换货政策',
      snippet: '顺丰标准件：1-3 个工作日送达，偏远地区 3-5 个工作日。',
      page: 1,
      index: 0,
    },
  ],
}
