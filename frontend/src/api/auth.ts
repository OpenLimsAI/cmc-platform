import { mdmApi, type ApiResponse } from './client'
import type { HubUser } from '@/stores/authStore'

// MDM POST /api/v1/auth/login 的 data 结构（见 cmab-mdm-platform LoginResponse）
export interface LoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: HubUser
}

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResult> => {
    const r = await mdmApi.post<ApiResponse<LoginResult>>('/auth/login', { username, password })
    return r.data.data
  },
  // 登出：撤销 MDM 侧 refresh token（失败也无所谓，本地态照清）
  logout: async (): Promise<void> => {
    try {
      await mdmApi.post('/auth/logout')
    } catch {
      /* ignore */
    }
  },
}
