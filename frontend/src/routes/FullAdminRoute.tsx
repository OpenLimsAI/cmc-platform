import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

/**
 * 仅全公司范围的管理员可进的系统管理子页（角色 / 权限 / 会话策略 / 部门管理员）。
 * 部门管理员（DEPT_ADMIN，范围=本部门）直接回到用户页，而不是进页面后看 403。
 */
export function FullAdminRoute() {
  const deptScoped = useAuthStore((s) => s.userAdminScope === 'department');
  if (deptScoped) return <Navigate to="/admin/users" replace />;
  return <Outlet />;
}
