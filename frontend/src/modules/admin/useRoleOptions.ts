import { useQuery } from '@tanstack/react-query';
import { adminRolesApi } from '@/api/admin';

/**
 * M5.2：角色下拉选项动态拉取（替代硬编码 ROLE_OPTIONS）。
 * 与库内角色始终一致——后端新增系统角色 / 管理员建自定义角色都会自动出现。
 * 系统角色排前；复用 ['admin-roles'] 缓存（与 RoleListPage 共享）。
 *
 * @param enabled 控制是否发起请求（如仅在抽屉打开时拉）
 */
export function useRoleOptions(enabled = true) {
  const { data: roles = [], isLoading } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: adminRolesApi.list,
    enabled,
  });

  const options = [...roles]
    .sort((a, b) => Number(b.is_system) - Number(a.is_system))
    .map((r) => ({ value: r.role_code, label: r.role_name }));

  return { options, isLoading, roles };
}
