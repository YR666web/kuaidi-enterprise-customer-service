import { defineStore } from 'pinia'

import { mockDashboard } from '@/mocks'
import { fetchDashboard } from '@/api/operations'
import type { DashboardMetrics } from '@/types'

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    metrics: mockDashboard as DashboardMetrics,
    loading: false,
  }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        const response = await fetchDashboard()
        this.metrics = response.data
      } catch {
        this.metrics = mockDashboard
      }
      this.loading = false
    },
  },
})
