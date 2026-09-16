import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Space, Typography } from 'antd'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { logoutReasonText, mdmLogin } from '@/shared/cmabSession'

export default function LoginPage() {
  const { status, user, error, reload } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [form] = Form.useForm<{ username: string; password: string }>()
  const [busy, setBusy] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const reason = logoutReasonText(params.get('reason'))

  const login = async ({ username, password }: { username: string; password: string }) => {
    setBusy(true)
    setLoginError(null)
    setMustChangePassword(false)
    try {
      const result = await mdmLogin(username, password)
      if (result.user.must_change_password) {
        setMustChangePassword(true)
      } else {
        navigate('/', { replace: true })
      }
    } catch (cause) {
      setLoginError(cause instanceof Error ? cause.message : '登录未完成')
    } finally {
      // 密码只交给 MDM，不保存在本系统的表单状态中等待下次使用。
      form.resetFields(['password'])
      setBusy(false)
    }
  }

  return (
    <Card title="使用 MDM 员工账号登录" style={{ maxWidth: 480, margin: '24px auto' }}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          登录由公司 MDM 身份中心验证。质量平台的查看和结构预览权限由服务端确认。
        </Typography.Paragraph>
        {reason && <Alert type="info" showIcon message={reason} />}
        {!status?.configured && <Alert type="warning" showIcon message="MDM 接入尚未就绪" description="请完成本机身份校验配置后重试；当前不能使用结构预览。" action={<Button onClick={reload}>重新检查</Button>} />}
        {(mustChangePassword || error) && <Alert type="warning" showIcon message={mustChangePassword ? '请先到 MDM 门户修改临时密码，再返回本系统。' : error} />}
        {loginError && <Alert type="error" showIcon message={loginError} />}
        {user && <Alert type="info" message={`当前身份：${user.full_name || user.username}`} description={user.can_preview || user.can_read ? '已由后端验证，可从左侧菜单进入已授权页面。' : '身份已验证，但尚未获得质量平台页面权限。'} />}
        <Form form={form} layout="vertical" onFinish={login} requiredMark={false}>
          <Form.Item label="员工工号" name="username" rules={[{ required: true, message: '请输入员工工号' }]}>
            <Input autoComplete="username" disabled={busy} />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="current-password" disabled={busy} />
          </Form.Item>
          <Button block type="primary" htmlType="submit" loading={busy} disabled={!status?.configured}>登录 MDM</Button>
        </Form>
        {status && !status.auth_required && <Link to="/release">返回本地只读开发页面</Link>}
      </Space>
    </Card>
  )
}
