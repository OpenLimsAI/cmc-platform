import type { LoginResponseUser } from '@/api/types';

export interface OidcConfig { enabled: boolean; native_login_enabled: boolean; signature_mode?: 'oidc_fresh'; device_logout_enabled?: boolean }
export interface OidcSession {
  mode: 'oidc';
  user: LoginResponseUser;
  expires_at: string;
  pm_delegated: boolean;
}
export interface OidcLogout {
  local_logout: boolean;
  global_logout: boolean;
  login_url: string;
  logout_url?: string;
  warning?: string;
}
