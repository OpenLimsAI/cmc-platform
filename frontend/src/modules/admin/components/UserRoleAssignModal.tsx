import { useEffect, useState } from 'react';
import { Modal, Select, Alert, Tag } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { adminUsersApi } from '@/api/admin';
import type { UserDetail } from '@/api/types';
import { useRoleOptions } from '../useRoleOptions';

interface Props {
  open: boolean;
  user: UserDetail | null;
  onClose: () => void;
  onSaved: (detail: UserDetail) => void;
}

export function UserRoleAssignModal({ open, user, onClose, onSaved }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const { options: roleOptions, isLoading: rolesLoading } = useRoleOptions(open);

  useEffect(() => {
    if (open && user) {
      setSelected(user.roles.map((r) => r.role_code));
    }
  }, [open, user]);

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
      okButtonProps={{ disabled: selected.length === 0 }}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="替换式分配：保存后将以下面的选择完全覆盖当前角色集合。"
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
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        placeholder="选择角色"
        value={selected}
        onChange={setSelected}
        loading={rolesLoading}
        options={roleOptions}
      />
    </Modal>
  );
}
