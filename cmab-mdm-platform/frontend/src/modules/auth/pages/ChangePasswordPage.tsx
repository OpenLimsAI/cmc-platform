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
import { useMutation, useQuery } from '@tanstack/react-query';
import { oidcApi } from '@/api/oidc';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';
import { passwordRules } from '@/shared/utils/passwordRules';
import { passwordChangeText } from '@/shared/passwordChangeText';

const { Title, Text } = Typography;

interface FormValues {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

export function ChangePasswordPage() {
  const signingConfig = useQuery({queryKey:['oidc-signing-config'],queryFn:oidcApi.config});
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const logout = useAuthStore((s) => s.logout);
  const clearMustChangePassword = useAuthStore((s) => s.clearMustChangePassword);
  const mustChangePassword = useAuthStore((s) => s.user?.must_change_password ?? false);
  const authMode = useAuthStore((s) => s.authMode);
  const nativeAllowed = useAuthStore((s) => s.nativeLoginEnabled);
  const copy = passwordChangeText(authMode, nativeAllowed);
  const [form] = Form.useForm<FormValues>();
  const isForced = mustChangePassword || searchParams.get('required') === '1';

  const mutation = useMutation({
    mutationFn: (payload: { old_password: string; new_password: string }) =>
      authApi.changePassword(payload),
    onSuccess: () => {
      message.success(copy.success);
      // 先清强制改密标记：否则这 3 秒内任何跳转都会被 ProtectedRoute 弹回本页
      clearMustChangePassword();
      // 后端 password_changed_at 更新后，旧 token 立即失效（M2.5.2）。
      // 主动登出 + 跳登录，避免后续请求触发 401 跳登录的二次跳转。
      // 带 changed=1 且**不带 redirect**：带 redirect 会在重新登录后把人送回本页，
      // 看起来就像"改完密码退不出去"（2026-09-10 验证部实际反馈）。
      setTimeout(() => {
        logout();
        navigate('/login?changed=1', { replace: true });
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

  if (signingConfig.data?.signature_mode === 'oidc_fresh') return <Alert type="info" message="密码由 Casdoor 管理。业务签名会在 Casdoor 页面重新认证，MDM 不再维护独立签名口令。" />;
  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '个人中心' }, { title: '修改密码' }]}
      />

      <Card style={{ maxWidth: 560 }}>
        <Title level={3} style={{ marginTop: 0 }}>
          {copy.heading}
        </Title>
        <p><Text type="secondary">{copy.description}</Text></p>

        {isForced && (
          <Alert
            type="error"
            showIcon
            message="当前密码需要更新"
            description="当前密码需要更新，完成改密后才能正常使用系统。新密码至少 8 位，包含大写、小写、数字和符号。"
            style={{ marginBottom: 16 }}
          />
        )}

        <Alert
          type="warning"
          showIcon
          message="改密后需要重新登录"
          description="密码修改成功后，此页面会自动退出登录。其他 MDM 登录会话也需要重新登录。"
          style={{ marginBottom: 20 }}
        />

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            label={copy.currentLabel}
            name="old_password"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>

          <Form.Item
            label={copy.newLabel}
            name="new_password"
            tooltip="至少 8 位，须包含大写、小写、数字和符号"
            rules={[
              { required: true, message: '请输入新密码' },
              ...passwordRules,
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
            label={copy.confirmLabel}
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
