import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminRolesApi } from '@/api/admin';
import type { RoleListItem } from '@/api/types';

/**
 * M5.2：角色下拉选项动态拉取（替代硬编码 ROLE_OPTIONS）。
 * 与库内角色始终一致——后端新增系统角色 / 管理员建自定义角色都会自动出现。
 * 系统角色排前；复用 ['admin-roles'] 缓存（与 RoleListPage 共享）。
 *
 * ⚠️ options / roles 必须是**稳定引用**：调用方会把它们放进 useEffect / useMemo 依赖，
 * 每次渲染新建数组会导致依赖恒变 → setState → 再渲染 → 无限循环（2026-09-10 分配角色弹窗事故）。
 * 所以这里用固定的 EMPTY 常量兜底 undefined，并用 useMemo 缓存 options。
 *
 * @param enabled 控制是否发起请求（如仅在抽屉打开时拉）
 */
const EMPTY_ROLES: RoleListItem[] = [];

export function useRoleOptions(enabled = true) {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: adminRolesApi.list,
    enabled,
  });

  const roles = data ?? EMPTY_ROLES;

  const options = useMemo(
    () =>
      [...roles]
        .sort((a, b) => Number(b.is_system) - Number(a.is_system))
        .map((r) => ({ value: r.role_code, label: r.role_name })),
    [roles],
  );

  return { options, isLoading, roles };
}
