import { ReactNode } from 'react';
import { useAuthStore } from '@/stores/authStore';

interface PermissionGuardProps {
  permission: string | string[];
  /** 多权限时的逻辑，默认 any（任意一个即可） */
  mode?: 'any' | 'all';
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * 权限守卫：缺少权限时渲染 fallback（默认 null）
 */
export function PermissionGuard({
  permission,
  mode = 'any',
  fallback = null,
  children,
}: PermissionGuardProps) {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const isAdmin = useAuthStore((s) => s.isAdmin);

  if (isAdmin) return <>{children}</>;

  const perms = Array.isArray(permission) ? permission : [permission];
  const ok =
    mode === 'all' ? perms.every((p) => hasPermission(p)) : perms.some((p) => hasPermission(p));

  return <>{ok ? children : fallback}</>;
}
