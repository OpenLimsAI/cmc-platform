/**
 * Phase 5.A / M5.1：管理员模块字典
 * M5.2 上线后 ROLE_OPTIONS 会改为从 `/api/v1/roles` 拉，目前用 seed 系统角色硬编码。
 * 注意：必须与 backend/app/scripts/seed_data.py 的 ROLES 同步（8 个系统角色）。
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
