import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { BASE, stripBase, withBase } from "../shared/base";
import { clearSession, getStoredToken, mdmRefresh } from "../shared/cmabSession";

// 默认 = /labops：所有 "/api/..." 调用实际发到 /labops/api/...，经 HUB nginx（或本地 vite 代理）剥掉 /labops 到后端
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || BASE;

// 认证（2026-09-04 起）：登录/续期/登出统一直接打 MDM（shared/cmabSession.ts），本客户端只负责
// 带令牌 + 401 时用 MDM refresh 兜底续一次并重放；主动续期与空闲登出由 MainLayout 里的会话守卫负责。
const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  withCredentials: true,
});

function forceLogout() {
  clearSession();
  if (stripBase(window.location.pathname) !== "/login") {
    window.location.href = withBase("/login?reason=expired");
  }
}

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getStoredToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 响应拦截器:401 兜底续期 + 重放原请求(只重试一次,防死循环)
client.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;
    // 登录接口自身的 401 不触发续期重放(否则登录密码错会被误当作会话失效)
    const url = original?.url ?? "";
    const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/refresh");

    if (status === 401 && original && !original._retried && !isAuthEndpoint) {
      original._retried = true;
      try {
        const newToken = await mdmRefresh();
        original.headers.Authorization = `Bearer ${newToken}`;
        return client(original); // 用新 token 重放原请求
      } catch {
        forceLogout();
        return Promise.reject(error);
      }
    }

    // 重放后仍 401(或无 config 可重放)→ 登出
    if (status === 401 && !isAuthEndpoint) {
      forceLogout();
    }
    return Promise.reject(error);
  },
);

export default client;
