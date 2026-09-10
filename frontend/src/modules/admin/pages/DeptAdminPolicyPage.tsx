/**
 * 系统管理 → 部门管理员（2026-09-10；migration 0055）
 * 配置「部门管理员（DEPT_ADMIN）可挂/摘的角色码前缀」白名单，保存即生效；变更进审计日志。
 * 权限 system:config（SYS_ADMIN 短路）。
 */
import { useEffect } from 'react';
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { SaveOutlined, TeamOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminRolesApi, adminSystemApi } from '@/api/admin';
import type { DeptAdminPolicy, DeptAdminPolicyUpdatePayload } from '@/api/types';
import { AdminTabs } from '../components/AdminTabs';

const { Title, Text } = Typography;

type FormValues = DeptAdminPolicyUpdatePayload;

const PREFIX_RE = /^[A-Z][A-Z0-9_]*$/;

function toFormValues(p: DeptAdminPolicy): FormValues {
  return { delegable_role_prefixes: p.delegable_role_prefixes, reason: '' };
}

export function DeptAdminPolicyPage() {
  const [form] = Form.useForm<FormValues>();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-dept-admin-policy'],
    queryFn: () => adminSystemApi.getDeptAdminPolicy(),
  });
  const { data: roles = [] } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: adminRolesApi.list,
  });

  useEffect(() => {
    if (data) form.setFieldsValue(toFormValues(data));
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: (payload: DeptAdminPolicyUpdatePayload) =>
      adminSystemApi.updateDeptAdminPolicy(payload),
    onSuccess: (saved) => {
      message.success('白名单已更新，部门管理员立即按新范围生效');
      queryClient.setQueryData(['admin-dept-admin-policy'], saved);
      queryClient.invalidateQueries({ queryKey: ['admin-audit-logs'] });
      form.setFieldsValue(toFormValues(saved));
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { message?: string } } };
      message.error(err.response?.data?.message || '保存失败');
    },
  });

  const prefixes = Form.useWatch('delegable_role_prefixes', form) ?? [];
  const protectedRoles = new Set(data?.protected_roles ?? ['SYS_ADMIN', 'DEPT_ADMIN']);
  const matched = roles.filter(
    (r) => !protectedRoles.has(r.role_code) && prefixes.some((p) => r.role_code.startsWith(p)),
  );

  const onFinish = (values: FormValues) => {
    mutation.mutate({
      delegable_role_prefixes: values.delegable_role_prefixes,
      reason: values.reason?.trim() || null,
    });
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '部门管理员' }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          <TeamOutlined style={{ marginRight: 8 }} />
          部门管理员可下放的角色
        </Title>
        <Text type="secondary">
          给部门负责人挂「部门管理员（DEPT_ADMIN）」角色后，他只能管理与自己同一部门的用户：
          查看、锁定/解锁、挂/摘下面白名单里的角色。新建用户、改资料、重置密码、改部门仍只有系统管理员能做。
        </Text>
      </Card>

      <Card>
        <AdminTabs />
        {error ? (
          <Alert type="error" showIcon message="读取白名单失败（需要 system:config 权限）" />
        ) : (
          <Form<FormValues>
            form={form}
            layout="vertical"
            onFinish={onFinish}
            disabled={isLoading}
            style={{ maxWidth: 640 }}
          >
            <Form.Item
              name="delegable_role_prefixes"
              label="允许下放的角色码前缀"
              extra="按前缀匹配角色码，输入后回车添加；例如 QV_ 会覆盖 QV_ADMIN / QV_ENGINEER / QV_REVIEWER / QV_VIEWER。留空 = 暂停下放。"
              rules={[
                {
                  validator: (_, value: string[] = []) => {
                    const bad = value.find((v) => !PREFIX_RE.test(v) || v.length > 32);
                    if (bad) {
                      return Promise.reject(
                        new Error(`前缀 ${bad} 不合法：须大写字母开头，仅含大写字母/数字/下划线`),
                      );
                    }
                    const hit = value.find((v) =>
                      [...protectedRoles].some((r) => r.startsWith(v)),
                    );
                    if (hit) {
                      return Promise.reject(new Error(`前缀 ${hit} 会覆盖受保护角色，不允许`));
                    }
                    return Promise.resolve();
                  },
                },
              ]}
            >
              <Select
                mode="tags"
                tokenSeparators={[',', ' ']}
                placeholder="例如 QV_"
                open={false}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item label="当前匹配到的角色（部门管理员下拉里会出现这些）">
              {matched.length ? (
                matched.map((r) => (
                  <Tag key={r.role_code} color="magenta">
                    {r.role_name}（{r.role_code}）
                  </Tag>
                ))
              ) : (
                <Text type="secondary">无——部门管理员暂时不能挂任何角色</Text>
              )}
            </Form.Item>

            <Form.Item name="reason" label="变更原因（可选，进审计日志）">
              <Input.TextArea
                rows={2}
                maxLength={500}
                showCount
                placeholder="例如：验证部平台上线，允许验证部负责人分配 QV_ 角色"
              />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SaveOutlined />}
                  loading={mutation.isPending}
                >
                  保存
                </Button>
                <Button onClick={() => data && form.setFieldsValue(toFormValues(data))}>
                  还原
                </Button>
              </Space>
            </Form.Item>
          </Form>
        )}

        {data && (
          <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
            <Descriptions.Item label="永不可下放">
              {data.protected_roles.map((r) => (
                <Tag key={r} color="red">
                  {r}
                </Tag>
              ))}
              <Text type="secondary">
                持有这两个角色的账号，部门管理员也不能锁定/解锁。
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="最近修改">
              {data.updated_at
                ? new Date(data.updated_at).toLocaleString('zh-CN', { hour12: false })
                : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="怎么给部门负责人开通">
              系统管理 → 用户 → 找到该负责人 → 分配角色 → 勾上「部门管理员（DEPT_ADMIN）」。
              前提：该负责人的「部门」字段已填写，并且与其要管理的人员部门完全一致。
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>
    </div>
  );
}
