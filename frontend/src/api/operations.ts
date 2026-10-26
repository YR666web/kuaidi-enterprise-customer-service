import http from './http'
import type { DashboardMetrics, FlowConfig, Session } from '@/types'

export function listSessions() {
  return http.get<Session[]>('/sessions')
}

export function updateSessionStatus(sessionId: string, status: Session['status']) {
  return http.patch<Session>(`/sessions/${sessionId}`, undefined, { params: { status } })
}

export function listFlows() {
  return http.get<FlowConfig[]>('/flows')
}

export function fetchDashboard() {
  return http.get<DashboardMetrics>('/dashboard')
}
