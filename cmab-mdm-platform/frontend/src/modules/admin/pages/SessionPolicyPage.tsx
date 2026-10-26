/**
 * 系统管理 → 会话策略（2026-09-04；migration 0054）
 * 四个时长在线可调，保存即生效（下一次登录/换证按新值）；变更进审计日志。
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
  InputNumber,
  Space,
  Typography,
  message,
} from 'antd';
import { ClockCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminSystemApi } from '@/api/admin';
import type { SessionPolicy, SessionPolicyUpdatePayload } from '@/api/types';
import { AdminTabs } from '../components/AdminTabs';

const { Title, Text } = Typography;

type FormValues = SessionPolicyUpdatePayload;

const FIELDS: {
  name: keyof Omit<SessionPolicyUpdatePayload, 'reason'>;
  label: string;
  unit: string;
  help: string;
}[] = [
  {
    name: 'idle_timeout_minutes',
    label: '空闲超时',
    unit: '分钟',
    help: '多久没有任何操作就自动退出登录、回到登录页。全公司各系统共用：在任一系统里有操作都算活跃。',
  },
  {
    name: 'absolute_max_hours',
    label: '单次登录最长时长',
    unit: '小时',
    help: '从登录那一刻算起，到点无论是否一直在用都必须重新登录。',
  },
  {
    name: 'access_token_minutes',
    label: '通行证有效期',
    unit: '分钟',
    help: '技术参数：通行证到期后系统会在后台自动换新，用户无感；不能大于空闲超时。一般不用改。',
  },
  {
    name: 'display_mode_idle_minutes',
    label: '展示模式空闲超时',
    unit: '分钟',
    help: '挂了「展示模式」角色的账号（墙屏/看板）用这个值代替上面的空闲超时。',
  },
];

function toFormValues(p: SessionPolicy): FormValues {
  return {
    access_token_minutes: p.access_token_minutes,
    idle_timeout_minutes: p.idle_timeout_minutes,
    absolute_max_hours: p.absolute_max_hours,
    display_mode_idle_minutes: p.display_mode_idle_minutes,
    reason: '',
  };
}

export function SessionPolicyPage() {
  const [form] = Form.useForm<FormValues>();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-session-policy'],
    queryFn: () => adminSystemApi.getSessionPolicy(),
  });

  useEffect(() => {
    if (data) form.setFieldsValue(toFormValues(data));
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: (payload: SessionPolicyUpdatePayload) => adminSystemApi.updateSessionPolicy(payload),
    onSuccess: (saved) => {
      message.success('会话策略已更新，下一次登录/续期起生效');
      queryClient.setQueryData(['admin-session-policy'], saved);
      queryClient.invalidateQueries({ queryKey: ['admin-audit-logs'] });
      form.setFieldsValue(toFormValues(saved));
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { message?: string } } };
      message.error(err.response?.data?.message || '保存失败');
    },
  });

  const onFinish = (values: FormValues) => {
    mutation.mutate({ ...values, reason: values.reason?.trim() || null });
  };

  const limits = data?.limits ?? {};

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '会话策略' }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          <ClockCircleOutlined style={{ marginRight: 8 }} />
          会话策略（自动登出时间）
        </Title>
        <Text type="secondary">
          一直在用就不掉线；放着不动超过「空闲超时」自动退出。这里的设置对门户和所有子系统统一生效，
          保存后立即生效，不用重启。
        </Text>
      </Card>

      <Card>
        <AdminTabs />
        {error ? (
          <Alert type="error" showIcon message="读取会话策略失败（需要 system:config 权限）" />
        ) : (
          <Form<FormValues>
            form={form}
            layout="vertical"
            onFinish={onFinish}
            disabled={isLoading}
            style={{ maxWidth: 640 }}
          >
            {FIELDS.map((f) => {
              const [min, max] = limits[f.name] ?? [1, 100000];
              return (
                <Form.Item
                  key={f.name}
                  name={f.name}
                  label={f.label}
                  extra={f.help}
                  rules={[
                    { required: true, message: `请输入${f.label}` },
                    { type: 'number', min, max, message: `范围 ${min}～${max} ${f.unit}` },
                  ]}
                >
                  <InputNumber min={min} max={max} precision={0} addonAfter={f.unit} style={{ width: 240 }} />
                </Form.Item>
              );
            })}
            <Form.Item name="reason" label="变更原因（可选，进审计日志）">
              <Input.TextArea rows={2} maxLength={500} showCount placeholder="例如：按 QA 要求把空闲超时从 30 改成 15 分钟" />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={mutation.isPending}>
                  保存
                </Button>
                <Button onClick={() => data && form.setFieldsValue(toFormValues(data))}>还原</Button>
              </Space>
            </Form.Item>
          </Form>
        )}

        {data && (
          <Descriptions size="small" column={1} style={{ marginTop: 8 }}>
            <Descriptions.Item label="最近修改">
              {data.updated_at ? new Date(data.updated_at).toLocaleString('zh-CN', { hour12: false }) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="说明">
              展示模式角色：系统管理 → 用户 → 给墙屏/看板账号挂「展示模式（DISPLAY_MODE）」角色即可，
              该角色本身不含任何业务权限，需与只读等角色一起挂。
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>
    </div>
  );
}
