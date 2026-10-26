import { defineStore } from 'pinia'

import { ROLE_PERMISSIONS, type Permission, type Role, type UserInfo } from '@/types'

const TOKEN_KEY = 'sl-token'
if (localStorage.getItem(TOKEN_KEY) === 'mock-token') localStorage.removeItem(TOKEN_KEY)

export const useAuthStore = defineStore('auth', {
  state: (): { token: string; user: UserInfo | null } => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem('sl-user') || 'null') as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s): Role => s.user?.role ?? 'admin',
    permissions: (s): Permission[] => ROLE_PERMISSIONS[s.user?.role ?? 'admin'] ?? [],
  },
  actions: {
    login(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem('sl-user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('sl-user')
    },
    switchRole(role: Role) {
      if (this.user) this.user = { ...this.user, role }
    },
    has(permission: Permission): boolean {
      if (this.permissions.includes('*')) return true
      return this.permissions.includes(permission)
    },
  },
})
