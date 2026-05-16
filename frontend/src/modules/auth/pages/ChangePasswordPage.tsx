import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Form,
  Input,
  Space,
  Typography,
  message,
} from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';

const { Title, Text } = Typography;

interface FormValues {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const logout = useAuthStore((s) => s.logout);
  const [form] = Form.useForm<FormValues>();
  const isForced = searchParams.get('required') === '1';

  const mutation = useMutation({
    mutationFn: (payload: { old_password: string; new_password: string }) =>
      authApi.changePassword(payload),
    onSuccess: () => {
      message.success('密码已修改，3 秒后将自动退出登录。请用新密码重新登录。');
      // 后端 password_changed_at 更新后，旧 token 立即失效（M2.5.2）。
      // 主动登出 + 跳登录，避免后续请求触发 401 跳登录的二次跳转。
      setTimeout(() => {
        logout();
        navigate('/login', { replace: true });
      }, 3000);
    },
    onError: (err: any) => {
      const errType = err?.response?.data?.meta?.error?.type;
      if (errType === 'old_password_wrong') {
        form.setFields([
          { name: 'old_password', errors: ['旧密码错误'] },
        ]);
      } else {
        message.error(err?.response?.data?.message ?? '修改密码失败');
      }
    },
  });

  const onFinish = (values: FormValues) => {
    mutation.mutate({
      old_password: values.old_password,
      new_password: values.new_password,
    });
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '个人中心' }, { title: '修改密码' }]}
      />

      <Card style={{ maxWidth: 560 }}>
        <Title level={3} style={{ marginTop: 0 }}>
          修改密码
        </Title>

        {isForced && (
          <Alert
            type="error"
            showIcon
            message="管理员已重置您的密码"
            description="此密码为一次性临时凭证，必须设置新密码后才能正常使用系统。新密码长度 ≥ 12 位，包含大小写、数字与符号。"
            style={{ marginBottom: 16 }}
          />
        )}

        <Alert
          type="warning"
          showIcon
          message="改密后旧登录凭证立即失效"
          description="为符合 21 CFR Part 11 §11.300（标识码/密码生命周期管理），密码变更后所有现存 access token 都会即时作废，包括其他浏览器/设备上的登录会话。提交成功后此页面会自动登出。"
          style={{ marginBottom: 20 }}
        />

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            label="当前密码"
            name="old_password"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>

          <Form.Item
            label="新密码"
            name="new_password"
            tooltip="至少 8 位，建议包含大小写字母 + 数字 + 特殊字符"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '新密码至少 8 位' },
              { max: 128 },
              {
                validator: (_, value) =>
                  value && value === form.getFieldValue('old_password')
                    ? Promise.reject(new Error('新密码不能与当前密码相同'))
                    : Promise.resolve(),
              },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
          </Form.Item>

          <Form.Item
            label="确认新密码"
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || value === getFieldValue('new_password')) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              提交修改
            </Button>
            {!isForced && (
              <Button onClick={() => navigate(-1)} disabled={mutation.isPending}>
                取消
              </Button>
            )}
          </Space>

          {mutation.isSuccess && (
            <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
              修改成功，正在退出登录...
            </Text>
          )}
        </Form>
      </Card>
    </div>
  );
}
