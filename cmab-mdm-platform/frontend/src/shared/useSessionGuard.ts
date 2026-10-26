/**
 * MDM 侧接入会话守卫（挂在 MainLayout，登录后的所有页面生效）
 * 通用逻辑在 sessionGuard.ts；这里只把 store / API / 路由接上。
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { message } from 'antd';
import { authApi } from '@/api/auth';
import { performRefresh } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { startSessionGuard, type LogoutReason } from './sessionGuard';
import { oidcApi } from '@/api/oidc';
import { authResultIsCurrent } from './oidcPolicy';

const REASON_TEXT: Record<LogoutReason, string | null> = {
  idle: '长时间未操作，已自动退出登录',
  expired: '登录已过期，请重新登录',
  'other-tab': null, // 别处已经提示过
};

export function useSessionGuard(): void {
  const navigate = useNavigate();
  const mode = useAuthStore((s) => s.authMode);

  useEffect(() => {
    if (mode === 'oidc') {
      let stopped = false;
      let checking = false;
      let lastActivity = Date.now();
      let idleMinutes = 30;
      const events = ['mousedown', 'keydown', 'touchstart', 'scroll', 'wheel'] as const;
      const activity = () => { lastActivity = Date.now(); };
      const end = (reason: 'idle' | 'expired') => {
        if (stopped) return;
        if (useAuthStore.getState().authExitReason === 'logout') return;
        stopped = true;
        useAuthStore.getState().logout(reason);
        message.warning(REASON_TEXT[reason]);
        navigate(`/login?reason=${reason}`, { replace: true });
      };
      const check = async () => {
        if (stopped || checking) return;
        const context = useAuthStore.getState();
        if (context.authExitReason) return;
        const epoch = context.authEpoch;
        checking = true;
        try {
          if (Date.now() - lastActivity > idleMinutes * 60000) {
            await oidcApi.logout(false).catch(() => undefined);
            end('idle');
            return;
          }
          const session = await oidcApi.session();
          const current = useAuthStore.getState();
          if (stopped || !authResultIsCurrent(epoch, current.authEpoch, current.authExitReason)) return;
          if (!session) { end('expired'); return; }
          current.setOidcSession(session.user, session.expires_at, session.pm_delegated, epoch);
        } catch {
          const current = useAuthStore.getState();
          if (authResultIsCurrent(epoch, current.authEpoch, current.authExitReason)) end('expired');
        } finally { checking = false; }
      };
      void authApi.sessionPolicy().then((policy) => { idleMinutes = policy.idle_timeout_minutes; }).catch(() => undefined);
      events.forEach((event) => window.addEventListener(event, activity, { passive: true }));
      const visible = () => { if (document.visibilityState === 'visible') void check(); };
      document.addEventListener('visibilitychange', visible);
      const timer = window.setInterval(() => { void check(); }, 30000);
      void check();
      return () => {
        stopped = true;
        window.clearInterval(timer);
        events.forEach((event) => window.removeEventListener(event, activity));
        document.removeEventListener('visibilitychange', visible);
      };
    }
    const stop = startSessionGuard({
      getToken: () => useAuthStore.getState().token,
      loadPolicy: () => authApi.sessionPolicy(),
      refresh: performRefresh,
      onTokenReplaced: (t) => useAuthStore.getState().updateToken(t),
      onLogout: (reason) => {
        const store = useAuthStore.getState();
        if (store.authExitReason === 'logout') return;
        if (store.token) {
          if (reason !== 'other-tab') void authApi.logout().catch(() => undefined);
          store.logout(reason === 'idle' ? 'idle' : 'expired');
        }
        const text = REASON_TEXT[reason];
        if (text) message.warning(text);
        navigate(`/login?reason=${reason}`, { replace: true });
      },
    });
    return stop;
  }, [mode, navigate]);
}
