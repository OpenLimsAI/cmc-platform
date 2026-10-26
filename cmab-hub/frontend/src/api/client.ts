import axios from 'axios'

import { authStore } from '@/stores/authStore'

// MDM 后端统一响应封装：{ code, message, data, meta }
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

// 门户自己不写后端：登录、取"我是谁"都直接打 MDM。
// 路径一律相对（/mdm/api/...），开发期由 Vite 代理、正式由 nginx 转到 MDM 后端，绝不写死 host:端口。
export const mdmApi = axios.create({
  baseURL: '/mdm/api/v1',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

mdmApi.interceptors.request.use((config) => {
  const t = authStore.get().token
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

// 从 MDM 错误响应里抠出可读的错误信息
export function errorMessage(err: unknown, fallback = '请求失败'): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return '连不上身份中心（MDM），请确认服务已启动'
    const data = err.response.data as Partial<ApiResponse<unknown>> | undefined
    return data?.message || `${fallback}（${err.response.status}）`
  }
  return fallback
}
