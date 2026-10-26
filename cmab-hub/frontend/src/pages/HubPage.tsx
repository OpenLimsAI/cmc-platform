import { LogoutOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Space, Tooltip } from 'antd'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { canAccess } from '@/auth/access'
import AppTile from '@/components/AppTile'
import { HUB_APPS } from '@/config/apps'
import { logoutToLogin, mdmLogout, startSessionGuard } from '@/shared/cmabSession'
import { useAuth } from '@/stores/authStore'

// 按时段问候（参考 Claude 首页的 "Evening, how are things?"）
function greeting(): { hello: string; sub: string } {
  const h = new Date().getHours()
  if (h < 5) return { hello: '夜深了', sub: '辛苦了，注意休息。' }
  if (h < 11) return { hello: '早上好', sub: '新的一天，从哪里开始？' }
  if (h < 13) return { hello: '中午好', sub: '先吃饭，事情不急。' }
  if (h < 18) return { hello: '下午好', sub: '今天想从哪里开始？' }
  return { hello: '晚上好', sub: '还在忙？挑一个进去吧。' }
}

export default function HubPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const visible = HUB_APPS.filter((a) => canAccess(a, user))
  // 管理员重置密码后发的是临时密码：改完之前哪个系统都不让进（2026-09-11，各后端同步拦）
  const mustChangePassword = Boolean(user?.must_change_password)
  // 没权限的应用直接不显示，也不提示「另有 N 个未显示」（负责人 2026-09-04）

  // 会话守卫：空闲超时自动登出 / 通行证快到期静默续期 / 别的标签页登出跟着退（规则由 MDM 会话策略配置）
  useEffect(() => startSessionGuard({ onLogout: logoutToLogin('/login') }), [])

  const logout = async () => {
    await mdmLogout() // 撤销 MDM refresh + 清全公司共用令牌（authStore 监听 cmab-token-changed 自动同步）
    navigate('/login', { replace: true })
  }

  return (
    <div className="hub">
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
        {mustChangePassword && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 20 }}
            message="你用的是临时密码，请先修改"
            description={
              <span>
                改完才能进其他系统（现在其他图标是灰的，点不开）。去 <a href="/mdm/">主数据 MDM</a> 修改。
              </span>
            }
          />
        )}

        <div className="hub-greeting">
          <h1>
            {greeting().hello}
            {user?.full_name ? `，${user.full_name}` : ''}
          </h1>
          <p>{greeting().sub}</p>
        </div>

        {visible.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message="你还没有任何应用的访问权限"
            description="请联系管理员在 MDM 后台为你的账号分配角色。"
          />
        ) : (
          <div
            className="tile-grid"
            style={{ '--cols': Math.min(visible.length, 4) } as React.CSSProperties}
          >
            {visible.map((a) => (
              // 临时密码没改之前，除 MDM 外一律锁住（后端也会 403，见各系统 auth）
              <AppTile key={a.id} app={a} locked={mustChangePassword && a.id !== 'mdm'} />
            ))}
          </div>
        )}

      </main>
    </div>
  )
}
