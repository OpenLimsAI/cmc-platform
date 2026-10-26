import { useEffect, type ReactNode } from 'react';
import { Alert, Button, Space, Spin } from 'antd';
import { oidcApi } from '@/api/oidc';
import { useAuthStore } from '@/stores/authStore';
import { restoreOidcAuth } from '@/shared/oidcBootstrap';
import { withBase } from '@/shared/base';

let bootstrap: Promise<void> | null = null;

export function AuthBootstrap({ children }: { children: ReactNode }) {
  const pending = useAuthStore((s) => s.bootstrapPending);
  const error = useAuthStore((s) => s.bootstrapError);
  const recoveryAllowed = useAuthStore((s) => s.oidcEnabled && s.nativeLoginEnabled);
  useEffect(() => {
    if (!bootstrap) {
      const native = window.location.pathname.endsWith('/login') && new URLSearchParams(window.location.search).get('native') === '1';
      bootstrap = restoreOidcAuth(oidcApi.config, oidcApi.session, useAuthStore.getState(), native);
    }
  }, []);
  if (pending) return <div style={{ padding: 80, textAlign: 'center' }}><Spin tip="正在确认登录状态" /></div>;
  if (error) return <div style={{ padding: 40 }}><Alert type="error" showIcon message={error} action={<Space><Button onClick={() => window.location.reload()}>重新检查</Button>{recoveryAllowed && <Button href={withBase('/login?native=1')}>原生密码恢复登录</Button>}</Space>} /></div>;
  return children;
}
