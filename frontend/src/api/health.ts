import http from './http'

export interface HealthResponse {
  status: string
  database?: string
  service?: string
  version?: string
}

/** 就绪探针：GET /health（相对 baseURL /api/v1）。 */
export function fetchHealth() {
  return http.get<HealthResponse>('/health')
}
