import { api, unwrap, unwrapList } from './client';
import type {
  LoginHistoryItem,
  LoginRequest,
  LoginResponse,
  SignatureItem,
  UserMe,
} from './types';

export const authApi = {
  login: (payload: LoginRequest) =>
    unwrap<LoginResponse>(api.post('/auth/login', payload)),

  me: () => unwrap<UserMe>(api.get('/auth/me')),

  logout: () => api.post('/auth/logout'),

  changePassword: (payload: { old_password: string; new_password: string }) =>
    unwrap<null>(api.post('/auth/change-password', payload)),

  // M5.4 个人中心
  myLoginHistory: (query: { page?: number; page_size?: number } = {}) =>
    unwrapList<LoginHistoryItem>(
      api.get('/auth/me/login-history', { params: query }),
    ),

  mySignatures: (query: { page?: number; page_size?: number } = {}) =>
    unwrapList<SignatureItem>(
      api.get('/auth/me/signatures', { params: query }),
    ),
};
