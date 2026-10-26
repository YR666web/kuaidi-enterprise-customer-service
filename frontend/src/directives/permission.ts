import type { Directive } from 'vue'

import { useAuthStore } from '@/stores/auth'

/**
 * 按钮级权限指令：v-permission="'knowledge:write'"
 * 无权限时从 DOM 移除该元素。
 */
export const permission: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    const required = binding.value
    if (required && !auth.has(required)) {
      el.parentNode?.removeChild(el)
    }
  },
}
