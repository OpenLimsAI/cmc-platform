import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

export function ProtectedRoute() {
  const token = useAuthStore((s) => s.token);
  const mustChangePassword = useAuthStore((s) => s.user?.must_change_password);
  const location = useLocation();

  if (!token) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  // 强制改密期间锁定在改密页（后端 get_current_user 同步有 403 权威拦截）
  if (mustChangePassword && location.pathname !== '/profile/password') {
    return <Navigate to="/profile/password?required=1" replace />;
  }

  return <Outlet />;
}
