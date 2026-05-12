import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { message as antdMessage } from 'antd';
import { useAuthStore } from '@/stores/authStore';
import type { ApiResponse, ApiErrorInfo } from './types';

// ============== 实例 ==============
export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// ============== 请求拦截器 ==============
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // 自动生成请求 ID（用于链路追踪）
    if (config.headers && !config.headers['X-Request-ID']) {
      config.headers['X-Request-ID'] = `req_${Date.now()}${Math.random().toString(36).slice(2, 8)}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ============== 响应拦截器 ==============
type BackendErrorBody = {
  code: number;
  message: string;
  data: null;
  meta: { error?: ApiErrorInfo };
};

api.interceptors.response.use(
  // 成功直接透传
  (response: AxiosResponse) => response,
  (error: AxiosError<BackendErrorBody>) => {
    // 网络错误
    if (!error.response) {
      antdMessage.error('网络异常，请检查网络连接');
      return Promise.reject(error);
    }

    const { status, data } = error.response;
    const errorMessage = data?.message || `请求失败（${status}）`;
    const errorType = data?.meta?.error?.type;

    // 401 未登录或 token 过期：清除状态并跳转登录
    // 例外：signature_invalid（电子签名密码错）不是会话失效，由调用方处理
    if (status === 401 && errorType !== 'signature_invalid') {
      const authStore = useAuthStore.getState();
      if (authStore.token) {
        antdMessage.warning('登录已过期，请重新登录');
        authStore.logout();
      }
      // 避免在登录页时还跳转
      if (!window.location.pathname.startsWith('/login')) {
        const redirect = encodeURIComponent(
          window.location.pathname + window.location.search
        );
        window.location.href = `/login?redirect=${redirect}`;
      }
      return Promise.reject(error);
    }

    // 403 权限不足
    if (status === 403) {
      antdMessage.error(errorMessage);
      return Promise.reject(error);
    }

    // 423 账户锁定
    if (status === 423) {
      antdMessage.error(errorMessage);
      return Promise.reject(error);
    }

    // 422 / 409 / 400 业务错误：在表单页通常自定义处理；这里统一兜底
    // 签名相关错误交给 StatusActionsBar 自己处理（避免重复 toast）
    if (status >= 400 && status < 500) {
      if (errorType === 'signature_invalid' || errorType === 'signature_required') {
        return Promise.reject(error);
      }
      // 校验错误：列出字段
      if (errorType === 'validation_failed' && data?.meta?.error?.details?.length) {
        const lines = data.meta.error.details
          .map((d) => `${d.field || ''} ${d.message}`.trim())
          .join('\n');
        antdMessage.error(`校验失败：${lines}`);
      } else {
        antdMessage.error(errorMessage);
      }
      return Promise.reject(error);
    }

    // 5xx 服务器错误
    antdMessage.error('服务器错误，请稍后重试或联系管理员');
    return Promise.reject(error);
  }
);

// ============== 工具方法 ==============
/** 解包后端 ApiResponse，直接返回 data 字段 */
export async function unwrap<T>(promise: Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  const res = await promise;
  return res.data.data;
}

/** 解包列表响应，返回 { items, pagination } */
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
