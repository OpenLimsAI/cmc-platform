import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

interface SessionActions {
  getToken: () => string | null
  refresh: () => Promise<string>
  clear: () => void
}

type RetryConfig = InternalAxiosRequestConfig & { _qapRetried?: boolean }

/** 401 仅续期并重放一次；403 包括临时密码限制，必须原样交给页面。 */
export function attachSessionInterceptors(client: AxiosInstance, session: SessionActions): void {
  client.interceptors.request.use((config) => {
    const token = session.getToken()
    if (token) config.headers.set('Authorization', `Bearer ${token}`)
    else config.headers.delete('Authorization')
    return config
  })

  client.interceptors.response.use(undefined, async (error) => {
    const config = error.config as RetryConfig | undefined
    if (error.response?.status !== 401 || !config) throw error
    if (config._qapRetried) {
      session.clear()
      throw error
    }
    config._qapRetried = true
    try {
      await session.refresh()
    } catch {
      session.clear()
      throw error
    }
    // 复用请求拦截器从统一存储读取刚换取的令牌，不保留旧 Authorization。
    return client.request(config)
  })
}
