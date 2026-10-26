import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { hasUiSession } from '@/shared/oidcPolicy';

/** 登录后不该被自动送回去的页面（送回去 = 用户以为"退不出来"） */
const NO_REDIRECT_BACK = ['/login', '/profile/password'];

export function ProtectedRoute() {
  const authenticated = useAuthStore((s) => hasUiSession(s.token, s.authMode, !!s.user));
  const mustChangePassword = useAuthStore((s) => s.user?.must_change_password);
  const location = useLocation();

  if (!authenticated) {
    const path = location.pathname;
    const keepRedirect = !NO_REDIRECT_BACK.some((p) => path.startsWith(p));
    if (!keepRedirect) return <Navigate to="/login" replace />;
    const redirect = encodeURIComponent(path + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  // 强制改密期间锁定在改密页（后端 get_current_user 同步有 403 权威拦截）
  if (mustChangePassword && location.pathname !== '/profile/password') {
    return <Navigate to="/profile/password?required=1" replace />;
  }

  return <Outlet />;
}
