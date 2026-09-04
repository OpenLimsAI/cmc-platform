/**
 * Phase 5.A / M5.1：管理员模块字典
 *
 * M5.2（已完成）：所有角色**下拉选项**改为动态拉取（见 `useRoleOptions`），
 * 不再依赖本文件。下方 ROLE_OPTIONS 仅作**标签展示映射**保留 ——
 * 用户列表角色 Tag 的中文名(ROLE_LABELS)与颜色(ROLE_COLORS)来源；
 * API 不携带颜色，故颜色须静态维护。未知/自定义角色 Tag 自动降级为
 * role_name + 默认色，不影响功能。新增系统角色时建议在此补一行配色。
 */
import type { UserStatus } from '@/api/types';

export const ROLE_OPTIONS: { value: string; label: string; color: string }[] = [
  { value: 'SYS_ADMIN', label: '系统管理员', color: 'red' },
  { value: 'SUBSTANCE_STEWARD', label: '物质数据管家', color: 'purple' },
  { value: 'PROJECT_MANAGER', label: '项目经理', color: 'blue' },
  { value: 'CMC_RESEARCHER', label: 'CMC 研究员', color: 'cyan' },
  { value: 'QA_REVIEWER', label: 'QA 审核', color: 'green' },
  { value: 'CMC_WAREHOUSE_ADMIN', label: '库管员', color: 'gold' },
  { value: 'CMC_EQUIPMENT_ADMIN', label: '设备管理员', color: 'geekblue' },
  { value: 'READ_ONLY_USER', label: '只读用户', color: 'default' },
  { value: 'DISPLAY_MODE', label: '展示模式', color: 'lime' },
];

export const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((r) => [r.value, r.label]),
);

export const ROLE_COLORS: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((r) => [r.value, r.color]),
);

export const USER_STATUS_OPTIONS: { value: UserStatus; label: string; color: string }[] = [
  { value: 'active', label: '正常', color: 'green' },
  { value: 'locked', label: '已锁定', color: 'orange' },
  { value: 'disabled', label: '已禁用', color: 'red' },
];

export const USER_STATUS_LABELS: Record<string, string> = Object.fromEntries(
  USER_STATUS_OPTIONS.map((s) => [s.value, s.label]),
);

export const USER_STATUS_COLORS: Record<string, string> = Object.fromEntries(
  USER_STATUS_OPTIONS.map((s) => [s.value, s.color]),
);
