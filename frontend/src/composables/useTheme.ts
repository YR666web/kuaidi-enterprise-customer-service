import { onMounted } from 'vue'

import { useAppStore } from '@/stores/app'

/** 应用主题到 DOM（data-theme + Element Plus dark class） */
export function useTheme() {
  const appStore = useAppStore()

  onMounted(() => {
    appStore.applyTheme()
  })

  return {
    isDark: () => appStore.isDark,
    toggle: () => appStore.toggleDark(),
  }
}
