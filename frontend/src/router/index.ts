import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/chat/ChatView.vue'),
    meta: { title: '用户对话端' },
  },
  {
    path: '/workbench',
    name: 'workbench',
    component: () => import('@/views/workbench/WorkbenchView.vue'),
    meta: { title: '客服工作台', roles: ['agent', 'operator', 'admin'] as Role[] },
  },
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { roles: ['operator', 'admin'] as Role[] },
    children: [
      {
        path: '',
        redirect: () => {
          const auth = useAuthStore()
          return auth.role === 'admin' ? '/admin/dashboard' : '/admin/knowledge'
        },
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { title: '数据看板', roles: ['admin'] as Role[] },
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识库' },
      },
      {
        path: 'flows',
        name: 'flows',
        component: () => import('@/views/admin/FlowsView.vue'),
        meta: { title: '流程配置' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/chat' },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 路由守卫：按角色过滤（无权限回对话端）+ 设置标题
router.beforeEach((to) => {
  const auth = useAuthStore()
  const roles = to.meta.roles as Role[] | undefined
  if (roles && roles.length && !roles.includes(auth.role)) {
    return { path: '/chat' }
  }
  if (to.meta.title) {
    document.title = `${to.meta.title as string} · 快递企业智能客服`
  }
})

export default router
