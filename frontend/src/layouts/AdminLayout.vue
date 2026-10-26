<template>
  <el-container class="admin">
    <el-aside :width="collapsed ? '64px' : '220px'" class="admin__aside">
      <div class="admin__logo" :class="{ 'admin__logo--collapsed': collapsed }">
        <span class="admin__logo-mark">栈</span>
        <span v-if="!collapsed" class="admin__logo-text">快递企业智能客服 · 运营后台</span>
      </div>
      <el-menu
        :collapse="collapsed"
        :default-active="route.path"
        router
        class="admin__menu"
      >
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="admin__header">
        <div class="admin__header-left">
          <el-icon class="admin__icon-btn" @click="appStore.toggleSidebar()">
            <Expand v-if="collapsed" />
            <Fold v-else />
          </el-icon>
          <span class="admin__page-title">{{ route.meta.title }}</span>
        </div>

        <div class="admin__header-right">
          <el-dropdown @command="navTo">
            <el-button text>
              端切换
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

          <el-icon class="admin__icon-btn" @click="appStore.toggleDark()">
            <Moon v-if="!appStore.isDark" />
            <Sunny v-else />
          </el-icon>

          <el-dropdown @command="onSwitchRole">
            <el-tag class="admin__role" type="info">{{ roleLabel }}</el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="operator">运营</el-dropdown-item>
                <el-dropdown-item command="admin">管理员</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown>
            <span class="admin__user">
              <el-avatar :size="28">{{ auth.user?.name?.[0] }}</el-avatar>
              <span class="admin__username">{{ auth.user?.name }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="auth.logout()">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="admin__main">
        <EmptyState
          v-if="!canViewCurrent"
          title="无访问权限"
          description="当前角色无权访问此页面"
        />
        <router-view v-else />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import {
  ArrowDown,
  DataLine,
  Document,
  Expand,
  Fold,
  Moon,
  SetUp,
  Sunny,
} from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import EmptyState from '@/components/common/EmptyState.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'

const appStore = useAppStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const collapsed = computed(() => appStore.sidebarCollapsed)

const roleLabel = computed(() => {
  const map: Record<Role, string> = { agent: '坐席', operator: '运营', admin: '管理员' }
  return map[auth.role]
})

// 按角色过滤菜单
const allMenus = [
  { path: '/admin/dashboard', title: '数据看板', icon: DataLine, roles: ['admin'] as Role[] },
  { path: '/admin/knowledge', title: '知识库', icon: Document, roles: ['operator', 'admin'] as Role[] },
  { path: '/admin/flows', title: '流程配置', icon: SetUp, roles: ['operator', 'admin'] as Role[] },
]
const menus = computed(() => allMenus.filter((m) => m.roles.includes(auth.role)))

// 当前角色是否有权访问当前页面（用于内容区无权限提示）
const canViewCurrent = computed(() => {
  const roles = route.meta.roles as Role[] | undefined
  if (!roles || roles.length === 0) return true
  return roles.includes(auth.role)
})

function navTo(path: string) {
  router.push(path)
}

function onSwitchRole(role: Role) {
  auth.switchRole(role)
  // 切换后若当前页无权限，自动跳到该角色能看的第一个菜单
  if (!canViewCurrent.value) {
    const first = menus.value[0]
    if (first) router.push(first.path)
  }
}
</script>

<style scoped lang="scss">
.admin {
  height: 100vh;
}
.admin__aside {
  background: var(--sl-bg-surface);
  border-right: 1px solid var(--sl-border);
  transition: width 0.2s ease;
  display: flex;
  flex-direction: column;
}
.admin__logo {
  display: flex;
  align-items: center;
  gap: var(--sl-space-sm);
  height: 60px;
  padding: 0 var(--sl-space-md);
  border-bottom: 1px solid var(--sl-border-light);
  overflow: hidden;
}
.admin__logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--sl-radius-md);
  background: var(--sl-primary);
  color: #fff;
  font-weight: var(--sl-font-weight-semibold);
  flex-shrink: 0;
}
.admin__logo-text {
  font-weight: var(--sl-font-weight-semibold);
  font-size: var(--sl-font-size-md);
  white-space: nowrap;
}
.admin__menu {
  border-right: none;
  padding: var(--sl-space-sm);
}
.admin__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 var(--sl-space-lg);
  background: var(--sl-bg-surface);
  border-bottom: 1px solid var(--sl-border);
}
.admin__header-left,
.admin__header-right {
  display: flex;
  align-items: center;
  gap: var(--sl-space-md);
}
.admin__page-title {
  font-size: var(--sl-font-size-lg);
  font-weight: var(--sl-font-weight-semibold);
}
.admin__icon-btn {
  font-size: 18px;
  color: var(--sl-text-secondary);
  cursor: pointer;
  transition: color 0.15s;

  &:hover {
    color: var(--sl-primary);
  }
}
.admin__role {
  cursor: pointer;
}
.admin__user {
  display: flex;
  align-items: center;
  gap: var(--sl-space-xs);
  cursor: pointer;
}
.admin__username {
  font-size: var(--sl-font-size-sm);
  color: var(--sl-text-regular);
}
.admin__main {
  background: var(--sl-bg-page);
  padding: var(--sl-space-lg);
  overflow: auto;
}
</style>
