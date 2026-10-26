import { useEffect } from 'react';
import { Alert, Button, Spin } from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { safeAuthReturnTo } from '@/shared/oidcPolicy';
import { useAuthStore } from '@/stores/authStore';

export function AuthCompletePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const mode = useAuthStore((s) => s.authMode);
  const mustChange = useAuthStore((s) => s.user?.must_change_password);
  useEffect(() => {
    if (mode === 'oidc') navigate(mustChange ? '/profile/password?required=1' : safeAuthReturnTo(params.get('return_to')) ?? '/', { replace: true });
  }, [mode, mustChange, navigate, params]);
  if (mode === 'oidc') return <Spin tip="正在进入主数据管理" />;
  return <Alert type="error" showIcon message="统一身份流程未建立有效的 MDM 会话" description="请重新登录；回调不会自动创建用户或分配业务权限。" action={<Button onClick={() => navigate('/login?oidc_error=session', { replace: true })}>返回登录</Button>} />;
}
