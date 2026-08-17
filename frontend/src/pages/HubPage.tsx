import { LogoutOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Space, Tooltip } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { authApi } from '@/api/auth'
import { canAccess } from '@/auth/access'
import AppTile from '@/components/AppTile'
import { HUB_APPS } from '@/config/apps'
import { authStore, useAuth } from '@/stores/authStore'

export default function HubPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  // 临时：磁贴风格预览开关 ?style=glass|bare|dark（默认 glass），负责人选定后收口成一种
  const [params] = useSearchParams()
  const style = params.get('style') || 'glass'

  const visible = HUB_APPS.filter((a) => canAccess(a, user))
  const hiddenCount = HUB_APPS.filter((a) => a.status !== 'hidden').length - visible.length

  const logout = async () => {
    await authApi.logout()
    authStore.set(null, null)
    navigate('/login', { replace: true })
  }

  return (
    <div className="hub" data-style={style}>
      <header className="hub-header">
        <div className="hub-brand">
          <span className="hub-logo">CMAB</span>
          <span className="hub-title">HUB</span>
        </div>
        <Space size="middle">
          <Tooltip title={user?.roles.length ? `角色：${user.roles.join(' / ')}` : '未分配角色'}>
            <span className="hub-user">
              <UserOutlined /> {user?.full_name}
              {user?.department ? <span className="hub-dept"> · {user.department}</span> : null}
            </span>
          </Tooltip>
          <Button icon={<LogoutOutlined />} onClick={logout}>
            退出
          </Button>
        </Space>
      </header>

      <main className="hub-main">
        {user?.must_change_password && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 20 }}
            message="你的密码需要修改"
            description={
              <span>
                请先到 <a href="/mdm/">主数据 MDM</a> 修改密码，再使用其他系统。
              </span>
            }
          />
        )}

        {visible.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message="你还没有任何应用的访问权限"
            description="请联系管理员在 MDM 后台为你的账号分配角色。"
          />
        ) : (
          <div className="tile-grid">
            {visible.map((a) => (
              <AppTile key={a.id} app={a} />
            ))}
          </div>
        )}

        {hiddenCount > 0 && (
          <span className="hub-note">另有 {hiddenCount} 个应用因权限不足未显示。</span>
        )}
      </main>
    </div>
  )
}
