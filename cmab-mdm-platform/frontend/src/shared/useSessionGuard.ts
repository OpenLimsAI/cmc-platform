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

const REASON_TEXT: Record<LogoutReason, string | null> = {
  idle: '长时间未操作，已自动退出登录',
  expired: '登录已过期，请重新登录',
  'other-tab': null, // 别处已经提示过
};

export function useSessionGuard(): void {
  const navigate = useNavigate();

  useEffect(() => {
    const stop = startSessionGuard({
      getToken: () => useAuthStore.getState().token,
      loadPolicy: () => authApi.sessionPolicy(),
      refresh: performRefresh,
      onTokenReplaced: (t) => useAuthStore.getState().updateToken(t),
      onLogout: (reason) => {
        const store = useAuthStore.getState();
        if (store.token) {
          if (reason !== 'other-tab') void authApi.logout().catch(() => undefined);
          store.logout();
        }
        const text = REASON_TEXT[reason];
        if (text) message.warning(text);
        navigate(`/login?reason=${reason}`, { replace: true });
      },
    });
    return stop;
  }, [navigate]);
}
