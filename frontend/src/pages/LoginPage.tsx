import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { authApi } from '@/api/auth'
import { errorMessage } from '@/api/client'
import { authStore, isTokenExpired, useAuth } from '@/stores/authStore'

interface FormValues {
  username: string
  password: string
}

export default function LoginPage() {
  const { token } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const redirect = params.get('redirect') || '/'
  if (token && !isTokenExpired(token)) return <Navigate to={redirect} replace />

  const onFinish = async (v: FormValues) => {
    setLoading(true)
    setError(null)
    try {
      // 账号密码原样交给 MDM 校验；门户不存密码、不签发令牌。
      const r = await authApi.login(v.username.trim(), v.password)
      authStore.set(r.access_token, r.user)
      navigate(redirect, { replace: true })
    } catch (e) {
      setError(errorMessage(e, '登录失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-bg">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">CMAB</div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            统一门户 HUB
          </Typography.Title>
          <Typography.Text type="secondary">一次登录，进入公司所有内部系统</Typography.Text>
        </div>

        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

        <Form<FormValues> layout="vertical" size="large" onFinish={onFinish} autoComplete="on">
          <Form.Item name="username" rules={[{ required: true, message: '请输入工号' }]}>
            <Input prefix={<UserOutlined />} placeholder="工号" autoFocus />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登 录
          </Button>
        </Form>

        <Typography.Paragraph type="secondary" style={{ marginTop: 20, marginBottom: 0, fontSize: 12 }}>
          账号与密码由主数据平台（MDM）统一管理；忘记密码请联系管理员。
        </Typography.Paragraph>
      </div>
    </div>
  )
}
