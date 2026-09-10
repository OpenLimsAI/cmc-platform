import { Navigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

/**
 * 首页落点（2026-09-10 负责人）：
 *  - 有任一主数据读权限 → 仪表盘
 *  - 只有部门管理员身份 → 用户管理
 *  - 其余（只用下游系统、MDM 内无权限的账号）→ 个人中心（改密码 / 登录记录）
 */
export function HomeRedirect() {
  const hasAnyRead = useAuthStore((s) => s.hasAnyReadPermission());
  const scope = useAuthStore((s) => s.userAdminScope);
  if (hasAnyRead) return <Navigate to="/dashboard" replace />;
  if (scope) return <Navigate to="/admin/users" replace />;
  return <Navigate to="/profile" replace />;
}
