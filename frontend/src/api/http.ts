import axios, { type AxiosError, type AxiosInstance, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

// 请求拦截：注入 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('sl-token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误兜底
http.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem('sl-token')
      localStorage.removeItem('sl-user')
      ElMessage.error('登录已过期，请重新登录')
    } else if (status === 403) {
      ElMessage.error(detail || '没有权限执行此操作')
    } else if (status && status >= 500) {
      ElMessage.error('服务异常，请稍后重试')
    } else {
      ElMessage.error(detail || error.message || '请求失败')
    }
    return Promise.reject(error)
  },
)

export default http
