import { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Alert } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';
import { APP_VERSION } from '@/shared/version';
import { touchActivity } from '@/shared/sessionGuard';

// 被会话守卫踢回登录页时的说明（?reason=idle|expired）
const REASON_NOTICE: Record<string, string> = {
  idle: '长时间未操作，已自动退出登录，请重新登录',
  expired: '登录已过期，请重新登录',
};

const { Title, Text } = Typography;

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const reasonNotice = REASON_NOTICE[searchParams.get('reason') ?? ''] ?? null;

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const result = await authApi.login(values);
      setAuth(result.access_token, result.user);
      touchActivity(); // 会话守卫的空闲计时从登录这一刻起算
      // 管理员重置后首次登录：强制跳改密页，绕过 redirect 目标（GxP）
      if (result.user.must_change_password) {
        message.warning('管理员已重置您的密码，请先设置新密码后再使用系统');
        navigate('/profile/password?required=1', { replace: true });
        return;
      }
      message.success(`欢迎回来，${result.user.full_name}`);
      const redirect = searchParams.get('redirect');
      navigate(redirect ? decodeURIComponent(redirect) : '/dashboard');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } } };
      setErrorMessage(err.response?.data?.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%)',
        padding: 24,
      }}
    >
      <div style={{ marginBottom: 40, textAlign: 'center' }}>
        <Title level={1} style={{ color: '#fff', marginBottom: 8 }}>
          CMAB MDM Portal
        </Title>
        <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: 16 }}>主数据管理平台</Text>
      </div>

      <Card style={{ width: 400, boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
        <Title level={3} style={{ marginTop: 0, marginBottom: 24, textAlign: 'center' }}>
          账号登录
        </Title>

        {reasonNotice && !errorMessage && (
          <Alert type="info" message={reasonNotice} showIcon style={{ marginBottom: 16 }} />
        )}

        {errorMessage && (
          <Alert
            type="error"
            message={errorMessage}
            showIcon
            style={{ marginBottom: 16 }}
            closable
            onClose={() => setErrorMessage(null)}
          />
        )}

        <Form name="login" onFinish={onFinish} autoComplete="off" size="large" layout="vertical">
          <Form.Item
            name="username"
            label="工号"
            rules={[{ required: true, message: '请输入工号' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="工号" autoFocus />
          </Form.Item>

          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登 录
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center', color: '#8c8c8c', fontSize: 13 }}>
            忘记密码？请联系系统管理员
          </div>
        </Form>
      </Card>

      <div style={{ marginTop: 32, color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>
        © 2026 CMAB · 系统版本 {APP_VERSION} · 内部系统
      </div>
    </div>
  );
}
