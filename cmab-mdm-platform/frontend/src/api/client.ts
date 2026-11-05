import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { message as antdMessage } from 'antd';
import { useAuthStore } from '@/stores/authStore';
import { BASE, stripBase, withBase } from '@/shared/base';
import type { ApiResponse, ApiErrorInfo } from './types';
import { authFailureLoginPath, authResultIsCurrent, mayRefreshNative } from '@/shared/oidcPolicy';
import { maySendBusinessWrite } from '@/shared/oidcSessionCheck';

// ============== 实例 ==============
export const api = axios.create({
  baseURL: `${BASE}/api/v1`, // = /mdm/api/v1：经 HUB nginx（或本地 vite 代理）剥掉 /mdm 到后端
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
  // P4.B：refresh token 走 HttpOnly Cookie，必须带 credentials 才能跨域携带
  withCredentials: true,
});

// 标记：内部触发的 refresh 请求 / 已重试过的请求，避免拦截器递归
interface RetryFlag {
  _skipAuthRefresh?: boolean;
  _retried?: boolean;
  _authEpoch?: number;
}
type AxiosRequestConfigEx = InternalAxiosRequestConfig & RetryFlag;

// ============== 请求拦截器 ==============
api.interceptors.request.use(
  (config: AxiosRequestConfigEx) => {
    const auth = useAuthStore.getState();
    if (!maySendBusinessWrite(auth.authMode, auth.oidcVerificationUnavailable, config.method)) {
      throw new axios.AxiosError('暂时无法核验登录状态，业务操作已暂停', 'ERR_SESSION_UNAVAILABLE', config);
    }
    config._authEpoch = auth.authEpoch;
    const token = auth.token;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.headers && !config.headers['X-Request-ID']) {
      config.headers['X-Request-ID'] = `req_${Date.now()}${Math.random().toString(36).slice(2, 8)}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ============== Refresh 串行化 ==============
// 同时多请求遇到 401 时，只触发一次 /auth/refresh；其他请求等待结果
let refreshPromise: Promise<string> | null = null;

export async function performRefresh(): Promise<string> {
  const context = useAuthStore.getState();
  if (!mayRefreshNative(context.authMode, context.authExitReason)) throw new Error('当前认证方式不允许原生换证');
  const epoch = context.authEpoch;
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const resp = await api.post(
        '/auth/refresh',
        null,
        { _skipAuthRefresh: true } as AxiosRequestConfigEx,
      );
      const newToken: string = resp.data.data.access_token;
      const current = useAuthStore.getState();
      if (!authResultIsCurrent(epoch, current.authEpoch, current.authExitReason) || current.authMode !== 'native') throw new Error('登录状态已改变');
      useAuthStore.getState().updateToken(newToken);
      return newToken;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

// 登录后不该被自动送回去的页面（与 routes/ProtectedRoute.tsx 同口径）：
// 改密页若被记成 redirect，用户改完密码重新登录会被送回改密页，像"退不出来"
function gotoLogin() {
  const path = stripBase(window.location.pathname); // 去掉 /mdm 前缀，redirect 只存站内相对路径
  if (path.startsWith('/login')) return;
  const target = authFailureLoginPath(path, window.location.search, useAuthStore.getState().authExitReason);
  window.location.replace(withBase(target));
}

// ============== 响应拦截器 ==============
type BackendErrorBody = {
  code: number;
  message: string;
  data: null;
  meta: { error?: ApiErrorInfo };
};

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError<BackendErrorBody>) => {
    const originalConfig = error.config as AxiosRequestConfigEx | undefined;
    const currentAuth = useAuthStore.getState();
    // A request dispatched before logout/login must not overwrite that transition.
    if (!authResultIsCurrent(originalConfig?._authEpoch, currentAuth.authEpoch, currentAuth.authExitReason)) return Promise.reject(error);
    if (error.code === 'ERR_SESSION_UNAVAILABLE') return Promise.reject(error);
    // 网络错误
    if (!error.response) {
      antdMessage.error('网络异常，请检查网络连接');
      return Promise.reject(error);
    }

    const { status, data } = error.response;
    const errorMessage = data?.message || `请求失败（${status}）`;
    const errorType = data?.meta?.error?.type;

    // 401 token_expired：尝试静默 refresh + retry
    // 排除：refresh 端点自身、已重试过的请求、电子签名 401（业务身份再验证）
    const isAuthRefreshUrl = originalConfig?.url?.includes('/auth/refresh');
    const canTryRefresh =
      mayRefreshNative(currentAuth.authMode, currentAuth.authExitReason) &&
      status === 401 &&
      errorType === 'token_expired' &&
      !!originalConfig &&
      !originalConfig._skipAuthRefresh &&
      !originalConfig._retried &&
      !isAuthRefreshUrl;

    if (canTryRefresh) {
      try {
        const newToken = await performRefresh();
        originalConfig._retried = true;
        if (originalConfig.headers) {
          originalConfig.headers.Authorization = `Bearer ${newToken}`;
        }
        return api(originalConfig);
      } catch {
        // refresh 失败 → 清状态跳登录
        const authStore = useAuthStore.getState();
        if (!authResultIsCurrent(originalConfig._authEpoch, authStore.authEpoch, authStore.authExitReason)) return Promise.reject(error);
        if (authStore.token || authStore.authMode === 'oidc') {
          antdMessage.warning('登录已过期，请重新登录');
          authStore.logout('expired');
        }
        gotoLogin();
        return Promise.reject(error);
      }
    }

    // 401 其他场景（token_missing / token_invalid / signature_invalid / old_password_wrong）
    if (status === 401) {
      // 业务型 401（身份再验证 / 旧密码错误），不是会话失效，交给调用方
      if (errorType === 'signature_invalid' || errorType === 'old_password_wrong') {
        return Promise.reject(error);
      }
      const authStore = useAuthStore.getState();
      if (authStore.token || authStore.authMode === 'oidc') {
        // refresh 端点自身的 401 带后端原话（「长时间未操作」/「已满 N 小时」），照抄给用户
        antdMessage.warning(
          isAuthRefreshUrl && errorType === 'token_expired' ? errorMessage : '登录已过期，请重新登录',
        );
        authStore.logout('expired');
      }
      gotoLogin();
      return Promise.reject(error);
    }

    // 403 权限不足
    if (status === 403) {
      if (errorType === 'password_change_required') {
        useAuthStore.getState().requirePasswordChange();
        if (stripBase(window.location.pathname) !== '/profile/password') {
          window.location.href = withBase('/profile/password?required=1');
        }
        return Promise.reject(error);
      }
      antdMessage.error(errorMessage);
      return Promise.reject(error);
    }

    // 423 账户锁定
    if (status === 423) {
      antdMessage.error(errorMessage);
      return Promise.reject(error);
    }

    // 422 / 409 / 400 业务错误
    if (status >= 400 && status < 500) {
      if (errorType === 'signature_invalid' || errorType === 'signature_required') {
        return Promise.reject(error);
      }
      // validation_failed：让 Form 调用方用 applyFormErrors 接管字段级红色高亮；
      // 拦截器不再统一 toast（避免与字段级提示重复）。caller 若不处理则什么都不出，
      // 但通常每个 mutation onError 都会 fallback 到 antdMessage.error。
      if (errorType === 'validation_failed' && data?.meta?.error?.details?.length) {
        return Promise.reject(error);
      }
      antdMessage.error(errorMessage);
      return Promise.reject(error);
    }

    // 5xx
    antdMessage.error('服务器错误，请稍后重试或联系管理员');
    return Promise.reject(error);
  }
);

// ============== 工具方法 ==============
export async function unwrap<T>(promise: Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  const res = await promise;
  return res.data.data;
}

export async function unwrapList<T>(
  promise: Promise<AxiosResponse<{ data: T[]; meta: { pagination?: import('./types').Pagination } }>>
): Promise<{ items: T[]; pagination: import('./types').Pagination }> {
  const res = await promise;
  return {
    items: res.data.data,
    pagination: res.data.meta.pagination ?? {
      page: 1,
      page_size: res.data.data.length,
      total: res.data.data.length,
      total_pages: 1,
    },
  };
}
