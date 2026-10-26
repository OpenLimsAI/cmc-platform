import type { LoginResponseUser } from '@/api/types';
import type { OidcConfig, OidcSession } from './oidcTypes';

interface RestoreActions {
  authEpoch?: number;
  setOidcConfig: (enabled: boolean, nativeEnabled: boolean) => void;
  setOidcSession: (user: LoginResponseUser, expiresAt: string, pmDelegated: boolean, expectedEpoch?: number) => void;
  finishBootstrap: (error?: string) => void;
}

export async function restoreOidcAuth(
  loadConfig: () => Promise<OidcConfig>,
  loadSession: () => Promise<OidcSession | null>,
  actions: RestoreActions,
  nativeRecovery = false,
): Promise<void> {
  try {
    const config = await loadConfig();
    actions.setOidcConfig(config.enabled, config.native_login_enabled);
    if (config.enabled && !nativeRecovery) {
      const session = await loadSession();
      if (session) actions.setOidcSession(session.user, session.expires_at, session.pm_delegated, actions.authEpoch);
    }
    actions.finishBootstrap();
  } catch {
    actions.finishBootstrap('无法确认当前登录配置或会话，请重试。未切换认证方式。');
  }
}
