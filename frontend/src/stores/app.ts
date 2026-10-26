import { defineStore } from 'pinia'

const THEME_KEY = 'sl-theme'

export const useAppStore = defineStore('app', {
  state: () => ({
    isDark: localStorage.getItem(THEME_KEY) === 'dark',
    sidebarCollapsed: false,
    backendOnline: false,
  }),
  actions: {
    toggleDark() {
      this.isDark = !this.isDark
      localStorage.setItem(THEME_KEY, this.isDark ? 'dark' : 'light')
      this.applyTheme()
    },
    applyTheme() {
      const el = document.documentElement
      el.setAttribute('data-theme', this.isDark ? 'dark' : 'light')
      el.classList.toggle('dark', this.isDark)
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    setBackendOnline(online: boolean) {
      this.backendOnline = online
    },
  },
})
