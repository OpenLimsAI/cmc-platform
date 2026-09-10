import { useEffect, useMemo, useState } from 'react';
import { Modal, Select, Alert, Tag } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { adminUsersApi } from '@/api/admin';
import type { UserDetail } from '@/api/types';
import { useRoleOptions } from '../useRoleOptions';

interface Props {
  open: boolean;
  user: UserDetail | null;
  /**
   * 部门管理员（DEPT_ADMIN）视角：/roles 只返回白名单角色，下拉只出这些；
   * 目标用户已有的非白名单角色显示为不可调整、保存时原样保留（后端同样保护）。
   */
  deptScoped?: boolean;
  onClose: () => void;
  onSaved: (detail: UserDetail) => void;
}

export function UserRoleAssignModal({ open, user, deptScoped = false, onClose, onSaved }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const { options: roleOptions, isLoading: rolesLoading } = useRoleOptions(open);

  const selectableCodes = useMemo(
    () => new Set(roleOptions.map((o) => o.value)),
    [roleOptions],
  );
  // 部门管理员碰不了的角色（不在白名单里）：只展示不可选
  const lockedRoles = useMemo(
    () =>
      deptScoped && user
        ? user.roles.filter((r) => !selectableCodes.has(r.role_code))
        : [],
    [deptScoped, user, selectableCodes],
  );

  useEffect(() => {
    if (open && user) {
      const codes = user.roles.map((r) => r.role_code);
      setSelected(deptScoped ? codes.filter((c) => selectableCodes.has(c)) : codes);
    }
  }, [open, user, deptScoped, selectableCodes]);

  const mutation = useMutation({
    mutationFn: () => adminUsersApi.assignRoles(user!.username, selected),
    onSuccess: (detail) => {
      onSaved(detail);
      onClose();
    },
  });

  return (
    <Modal
      title={`分配角色 — ${user?.username ?? ''}`}
      open={open}
      onCancel={onClose}
      onOk={() => mutation.mutate()}
      confirmLoading={mutation.isPending}
      okText="保存"
      cancelText="取消"
      okButtonProps={{ disabled: rolesLoading || (!deptScoped && selected.length === 0) }}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message={
          deptScoped
            ? '只能调整允许下放的角色；下面标为「不可调整」的角色会原样保留。'
            : '替换式分配：保存后将以下面的选择完全覆盖当前角色集合。'
        }
      />
      <div style={{ marginBottom: 8, color: '#8c8c8c' }}>
        当前角色：
        {user?.roles?.length ? (
          user.roles.map((r) => (
            <Tag key={r.role_code} style={{ marginLeft: 4 }}>
              {r.role_name}
            </Tag>
          ))
        ) : (
          <Tag color="default">无</Tag>
        )}
      </div>
      {lockedRoles.length > 0 && (
        <div style={{ marginBottom: 8, color: '#8c8c8c' }}>
          不可调整：
          {lockedRoles.map((r) => (
            <Tag key={r.role_code} color="default" style={{ marginLeft: 4 }}>
              {r.role_name}
            </Tag>
          ))}
        </div>
      )}
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        placeholder={deptScoped ? '选择允许下放的角色' : '选择角色'}
        value={selected}
        onChange={setSelected}
        loading={rolesLoading}
        options={roleOptions}
      />
    </Modal>
  );
}
