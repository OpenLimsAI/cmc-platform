import type { LoginResponseUser } from '@/api/types';
import type { OidcConfig, OidcSession } from './oidcTypes';

interface RestoreActions {
  authEpoch?: number;
  setOidcConfig: (enabled: boolean, nativeEnabled: boolean) => number | void;
  setOidcSession: (user: LoginResponseUser, expiresAt: string, pmDelegated: boolean, expectedEpoch?: number) => void;
  finishBootstrap: (error?: string) => void;
}

function isExpiredBootstrapPassword(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false;
  const response = (error as { response?: { status?: unknown; data?: { code?: unknown } } }).response;
  return response?.status === 403 && response.data?.code === 40308;
}

export async function restoreOidcAuth(
  loadConfig: () => Promise<OidcConfig>,
  loadSession: () => Promise<OidcSession | null>,
  actions: RestoreActions,
  nativeRecovery = false,
): Promise<void> {
  try {
    const config = await loadConfig();
    const policyEpoch = actions.setOidcConfig(config.enabled, config.native_login_enabled);
    if (config.enabled && !(nativeRecovery && config.native_login_enabled)) {
      let session: OidcSession | null;
      try {
        session = await loadSession();
      } catch (error) {
        // This exact refusal follows server-side OIDC verification. Preserve the
        // gate; never restore an identity or display arbitrary response text.
        if (!isExpiredBootstrapPassword(error)) throw error;
        const password = config.native_login_enabled ? 'MDM 临时密码' : 'MDM 初始签名密码';
        actions.finishBootstrap(`Casdoor 身份已验证，但 ${password}已过期，暂时无法进入应用。请联系管理员通过安全渠道重新发放。不要在 MDM 输入 Casdoor 密码。`);
        return;
      }
      if (session) actions.setOidcSession(session.user, session.expires_at, session.pm_delegated,
        typeof policyEpoch === 'number' ? policyEpoch : actions.authEpoch);
    }
    actions.finishBootstrap();
  } catch {
    actions.finishBootstrap('无法确认当前登录配置或会话，请重试。未切换认证方式。');
  }
}
