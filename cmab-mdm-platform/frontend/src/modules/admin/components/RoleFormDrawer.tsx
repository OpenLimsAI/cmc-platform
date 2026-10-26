import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Space,
  Tag,
  Transfer,
} from 'antd';
import type { TransferProps } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { adminPermissionsApi, adminRolesApi } from '@/api/admin';
import type { RoleDetail } from '@/api/types';
import { applyFormErrors } from '@/shared/utils/formErrors';

type Mode = 'create' | 'edit';

interface Props {
  open: boolean;
  mode: Mode;
  role?: RoleDetail | null;
  onClose: () => void;
  onSaved: (detail: RoleDetail) => void;
}

interface PermItem {
  key: string;
  title: string;
  description: string;
}

export function RoleFormDrawer({ open, mode, role, onClose, onSaved }: Props) {
  const [form] = Form.useForm();
  const [targetKeys, setTargetKeys] = useState<string[]>([]);

  const { data: permissions = [] } = useQuery({
    queryKey: ['admin-permissions'],
    queryFn: () => adminPermissionsApi.list(),
    enabled: open,
  });

  const dataSource: PermItem[] = useMemo(
    () =>
      permissions.map((p) => ({
        key: p.permission_code,
        title: p.permission_code,
        description: p.description ?? '',
      })),
    [permissions],
  );

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && role) {
      form.setFieldsValue({
        role_code: role.role_code,
        role_name: role.role_name,
        description: role.description,
      });
      setTargetKeys(role.permissions.map((p) => p.permission_code));
    } else {
      form.resetFields();
      setTargetKeys([]);
    }
  }, [open, mode, role, form]);

  const createMutation = useMutation({
    mutationFn: adminRolesApi.create,
    onSuccess: (detail) => {
      onSaved(detail);
      onClose();
    },
    onError: (err) => applyFormErrors(form, err),
  });

  const updateMutation = useMutation({
    mutationFn: (values: { role_name: string; description?: string | null }) =>
      adminRolesApi.update(role!.role_code, {
        role_name: values.role_name,
        description: values.description ?? null,
        permission_codes: targetKeys,
      }),
    onSuccess: (detail) => {
      onSaved(detail);
      onClose();
    },
    onError: (err) => applyFormErrors(form, err),
  });

  const onFinish = (values: Record<string, unknown>) => {
    if (mode === 'create') {
      createMutation.mutate({
        role_code: values.role_code as string,
        role_name: values.role_name as string,
        description: (values.description as string) ?? null,
        permission_codes: targetKeys,
      });
    } else {
      updateMutation.mutate({
        role_name: values.role_name as string,
        description: (values.description as string) ?? null,
      });
    }
  };

  const submitting = createMutation.isPending || updateMutation.isPending;

  const filterOption: TransferProps['filterOption'] = (input, item) =>
    item.key.toLowerCase().includes(input.toLowerCase()) ||
    item.description.toLowerCase().includes(input.toLowerCase());

  return (
    <Drawer
      title={mode === 'create' ? '新建自定义角色' : `编辑角色 — ${role?.role_code}`}
      width={720}
      open={open}
      onClose={onClose}
      destroyOnClose
      maskClosable={!submitting}
      extra={
        <Space>
          <Button onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button type="primary" loading={submitting} onClick={() => form.submit()}>
            保存
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={
          mode === 'create'
            ? '角色编码（role_code）创建后不可修改。建议使用 ALL_CAPS_WITH_UNDERSCORE 风格。'
            : '角色编码不可修改。可调整名称、描述与权限集合。'
        }
      />

      <Form form={form} layout="vertical" onFinish={onFinish} autoComplete="off">
        <Form.Item
          name="role_code"
          label="角色编码"
          rules={[
            { required: true, message: '请输入角色编码' },
            {
              pattern: /^[A-Z][A-Z0-9_]+$/,
              message: '以大写字母开头，仅含大写、数字、下划线',
            },
            { min: 3, max: 32 },
          ]}
        >
          <Input disabled={mode === 'edit'} placeholder="如 ANALYTICAL_LEAD" />
        </Form.Item>

        <Form.Item
          name="role_name"
          label="角色名称"
          rules={[{ required: true, message: '请输入角色名称' }]}
        >
          <Input placeholder="如 分析方法负责人" />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="此角色的职责说明" />
        </Form.Item>

        <Form.Item label={<span>权限集合（已选 <Tag color="blue">{targetKeys.length}</Tag>）</span>}>
          <Transfer
            dataSource={dataSource}
            targetKeys={targetKeys}
            onChange={(keys) => setTargetKeys(keys as string[])}
            render={(item) => `${item.title}${item.description ? ` — ${item.description}` : ''}`}
            showSearch
            filterOption={filterOption}
            listStyle={{ width: 300, height: 360 }}
            titles={['可选权限', '已选权限']}
            locale={{
              itemUnit: '项',
              itemsUnit: '项',
              searchPlaceholder: '搜索权限码或描述',
            }}
          />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
