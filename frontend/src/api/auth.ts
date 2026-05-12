import { api, unwrap } from './client';
import type { LoginRequest, LoginResponse, UserMe } from './types';

export const authApi = {
  login: (payload: LoginRequest) =>
    unwrap<LoginResponse>(api.post('/auth/login', payload)),

  me: () => unwrap<UserMe>(api.get('/auth/me')),

  logout: () => api.post('/auth/logout'),

  changePassword: (payload: { old_password: string; new_password: string }) =>
    unwrap<null>(api.post('/auth/change-password', payload)),
};
