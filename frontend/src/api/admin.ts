/**
 * 管理员侧 API（Phase 5.A / M5.1）：用户/角色/权限管理
 * 权限：user:manage / role:manage
 */
import { api, unwrap, unwrapList } from './client';
import type {
  AuditLogItem,
  AuditLogQuery,
  DeptAdminPolicy,
  DeptAdminPolicyUpdatePayload,
  PermissionItem,
  ResetPasswordResult,
  RoleCreatePayload,
  RoleDetail,
  RoleListItem,
  RoleUpdatePayload,
  SessionPolicy,
  SessionPolicyUpdatePayload,
  SignatureItem,
  SignatureQuery,
  UserCreatePayload,
  UserDetail,
  UserListItem,
  UserListQuery,
  UserUpdatePayload,
} from './types';

export const adminUsersApi = {
  list: (query: UserListQuery = {}) =>
    unwrapList<UserListItem>(api.get('/users', { params: query })),

  get: (username: string) =>
    unwrap<UserDetail>(api.get(`/users/${encodeURIComponent(username)}`)),

  create: (payload: UserCreatePayload) =>
    unwrap<UserDetail>(api.post('/users', payload)),

  update: (username: string, payload: UserUpdatePayload) =>
    unwrap<UserDetail>(
      api.put(`/users/${encodeURIComponent(username)}`, payload),
    ),

  assignRoles: (username: string, role_codes: string[]) =>
    unwrap<UserDetail>(
      api.put(`/users/${encodeURIComponent(username)}/roles`, { role_codes }),
    ),

  lock: (username: string) =>
    unwrap<UserDetail>(
      api.post(`/users/${encodeURIComponent(username)}:lock`),
    ),

  unlock: (username: string) =>
    unwrap<UserDetail>(
      api.post(`/users/${encodeURIComponent(username)}:unlock`),
    ),

  resetPassword: (username: string) =>
    unwrap<ResetPasswordResult>(
      api.post(`/users/${encodeURIComponent(username)}:reset-password`),
    ),
};

export const adminRolesApi = {
  list: () => unwrap<RoleListItem[]>(api.get('/roles')),

  get: (role_code: string) =>
    unwrap<RoleDetail>(api.get(`/roles/${encodeURIComponent(role_code)}`)),

  create: (payload: RoleCreatePayload) =>
    unwrap<RoleDetail>(api.post('/roles', payload)),

  update: (role_code: string, payload: RoleUpdatePayload) =>
    unwrap<RoleDetail>(
      api.put(`/roles/${encodeURIComponent(role_code)}`, payload),
    ),

  delete: (role_code: string) =>
    api.delete(`/roles/${encodeURIComponent(role_code)}`),
};

export const adminPermissionsApi = {
  list: () => unwrap<PermissionItem[]>(api.get('/permissions')),
};

export const adminAuditApi = {
  list: (query: AuditLogQuery = {}) =>
    unwrapList<AuditLogItem>(api.get('/audit-logs', { params: query })),

  /** 触发 CSV 下载（浏览器侧）。POST + responseType=blob */
  exportCsv: async (query: AuditLogQuery = {}): Promise<{ blob: Blob; filename: string; rowCount: number }> => {
    const resp = await api.post('/audit-logs:export', null, {
      params: query,
      responseType: 'blob',
    });
    // 解析 Content-Disposition 取 filename
    const cd: string = resp.headers['content-disposition'] ?? '';
    const match = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
    const filename = match ? decodeURIComponent(match[1].replace(/^"|"$/g, '')) : 'audit_logs.csv';
    return {
      blob: resp.data as Blob,
      filename,
      rowCount: parseInt(resp.headers['x-row-count'] ?? '0', 10),
    };
  },
};

export const adminSignaturesApi = {
  list: (query: SignatureQuery = {}) =>
    unwrapList<SignatureItem>(api.get('/signatures', { params: query })),
};

/** 会话策略（权限 system:config；SYS_ADMIN 短路） */
export const adminSystemApi = {
  getSessionPolicy: () => unwrap<SessionPolicy>(api.get('/system/session-policy')),
  updateSessionPolicy: (payload: SessionPolicyUpdatePayload) =>
    unwrap<SessionPolicy>(api.put('/system/session-policy', payload)),
  /** 部门管理员可下放角色前缀白名单（权限 system:config） */
  getDeptAdminPolicy: () => unwrap<DeptAdminPolicy>(api.get('/system/dept-admin-policy')),
  updateDeptAdminPolicy: (payload: DeptAdminPolicyUpdatePayload) =>
    unwrap<DeptAdminPolicy>(api.put('/system/dept-admin-policy', payload)),
};
