import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { BASE, TOKEN_KEY, USER_KEY, stripBase, withBase } from "../shared/base";

// 默认 = /labops：所有 "/api/..." 调用实际发到 /labops/api/...，经 HUB nginx（或本地 vite 代理）剥掉 /labops 到后端
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || BASE;

// 主客户端:携带 refresh Cookie(withCredentials),并挂续期拦截器
const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  withCredentials: true,
});

// 裸客户端:仅用于调 /auth/refresh,不挂续期拦截器,避免递归
const bare = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  withCredentials: true,
});

const REFRESH_AHEAD_MS = 5 * 60 * 1000; // access 剩余 < 5 分钟时主动续期

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/** 解 JWT 的 exp(毫秒);解析失败返回 0(当作不过期,交给 401 兜底)。 */
function tokenExpMs(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload?.exp ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

function forceLogout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  if (stripBase(window.location.pathname) !== "/login") {
    window.location.href = withBase("/login");
  }
}

// 并发控制:同一时刻只发起一次 refresh,其余请求等待同一个 promise
let refreshPromise: Promise<string> | null = null;

function doRefresh(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = bare
      .post("/api/auth/refresh")
      .then((resp) => {
        const newToken: string | undefined = resp.data?.access_token;
        if (!newToken) throw new Error("refresh 未返回 access_token");
        localStorage.setItem(TOKEN_KEY, newToken);
        return newToken;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// 请求拦截器:带 token;若 access 快过期则先主动续期
client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  let token = getToken();
  if (token) {
    const exp = tokenExpMs(token);
    if (exp && exp - Date.now() < REFRESH_AHEAD_MS) {
      try {
        token = await doRefresh();
      } catch {
        // 主动续期失败:放行用原 token,由响应 401 兜底再处理
      }
    }
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
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
    // 登录/续期接口自身的 401 不触发续期重放(否则登录密码错会被误当作会话失效)
    const url = original?.url ?? "";
    const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/refresh");

    if (status === 401 && original && !original._retried && !isAuthEndpoint) {
      original._retried = true;
      try {
        const newToken = await doRefresh();
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
