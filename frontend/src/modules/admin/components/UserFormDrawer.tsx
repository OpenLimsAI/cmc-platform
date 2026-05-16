import { useEffect } from 'react';
import { Drawer, Form, Input, Select, Button, Space, Alert } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { adminUsersApi } from '@/api/admin';
import type { UserDetail } from '@/api/types';
import { applyFormErrors } from '@/shared/utils/formErrors';
import { ROLE_OPTIONS } from '../constants';

type Mode = 'create' | 'edit';

interface Props {
  open: boolean;
  mode: Mode;
  user?: UserDetail | null;
  onClose: () => void;
  onSaved: (detail: UserDetail) => void;
}

export function UserFormDrawer({ open, mode, user, onClose, onSaved }: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && user) {
      form.setFieldsValue({
        username: user.username,
        email: user.email,
        full_name: user.full_name,
        full_name_en: user.full_name_en,
        department: user.department,
        title: user.title,
        phone: user.phone,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({ role_codes: ['READ_ONLY_USER'] });
    }
  }, [open, mode, user, form]);

  const createMutation = useMutation({
    mutationFn: adminUsersApi.create,
    onSuccess: (detail) => {
      onSaved(detail);
      onClose();
    },
    onError: (err) => applyFormErrors(form, err),
  });

  const updateMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      adminUsersApi.update(user!.username, values),
    onSuccess: (detail) => {
      onSaved(detail);
      onClose();
    },
    onError: (err) => applyFormErrors(form, err),
  });

  const onFinish = async (values: Record<string, unknown>) => {
    if (mode === 'create') {
      createMutation.mutate(values as never);
    } else {
      // 编辑模式：仅 profile 字段，username/password/role 走专用流程
      const { username: _u, password: _p, role_codes: _r, ...rest } = values;
      updateMutation.mutate(rest);
    }
  };

  const submitting = createMutation.isPending || updateMutation.isPending;

  return (
    <Drawer
      title={mode === 'create' ? '新建用户' : `编辑用户 — ${user?.username}`}
      width={520}
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
      {mode === 'edit' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="此处仅修改基本信息。修改用户名不被支持，重置密码 / 角色分配 / 锁定请使用列表操作菜单。"
        />
      )}

      <Form form={form} layout="vertical" onFinish={onFinish} autoComplete="off">
        <Form.Item
          name="username"
          label="用户名"
          rules={[
            { required: true, message: '请输入用户名' },
            {
              pattern: /^[a-zA-Z][a-zA-Z0-9_.-]+$/,
              message: '以字母开头，仅含字母数字 _ . -',
            },
            { min: 3, max: 64 },
          ]}
        >
          <Input disabled={mode === 'edit'} placeholder="登录用户名" />
        </Form.Item>

        <Form.Item
          name="email"
          label="邮箱"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' },
          ]}
        >
          <Input placeholder="user@cmab.com" />
        </Form.Item>

        {mode === 'create' && (
          <Form.Item
            name="password"
            label="初始密码"
            extra="≥12 字符，包含大小写、数字、符号"
            rules={[
              { required: true, message: '请输入初始密码' },
              { min: 12, message: '密码至少 12 位' },
            ]}
          >
            <Input.Password placeholder="请输入初始密码" />
          </Form.Item>
        )}

        <Form.Item
          name="full_name"
          label="姓名"
          rules={[{ required: true, message: '请输入姓名' }]}
        >
          <Input placeholder="中文姓名" />
        </Form.Item>

        <Form.Item name="full_name_en" label="英文姓名">
          <Input placeholder="English Name" />
        </Form.Item>

        <Form.Item name="department" label="部门">
          <Input placeholder="如 CMC R&D / QA" />
        </Form.Item>

        <Form.Item name="title" label="职位">
          <Input placeholder="如 Senior Scientist" />
        </Form.Item>

        <Form.Item name="phone" label="电话">
          <Input placeholder="可选" />
        </Form.Item>

        {mode === 'create' && (
          <Form.Item
            name="role_codes"
            label="角色"
            rules={[{ required: true, message: '至少选择一个角色' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择角色"
              options={ROLE_OPTIONS.map((r) => ({ value: r.value, label: r.label }))}
            />
          </Form.Item>
        )}
      </Form>
    </Drawer>
  );
}
