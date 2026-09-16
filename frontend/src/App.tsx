import { useEffect, useState, type ReactNode } from 'react'
import { Alert, Button, Layout, Menu, Typography, Tag, Space, Spin } from 'antd'
import { Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import ReleaseTrendPage from './pages/ReleaseTrendPage'
import StabilityPage from './pages/StabilityPage'
import LoginPage from './pages/LoginPage'
import ImportPreviewPage from './pages/ImportPreviewPage'
import { useAuth } from './auth/AuthProvider'
import { SidebarHost } from './components/SidebarSlot'
import './app.css'

const { Header } = Layout
const { Title, Paragraph } = Typography

function Placeholder({ name }: { name: string }) {
  return (
    <Typography>
      <Title level={3}>{name}</Title>
      <Paragraph type="secondary">正在按旧看板补齐分析流程，暂未开放。可先查看放行趋势。</Paragraph>
    </Typography>
  )
}

function HealthBadge() {
  const [ok, setOk] = useState<boolean | null>(null)
  useEffect(() => {
    fetch('/health')
      .then((r) => r.json())
      .then((j) => setOk(j?.data?.status === 'ok'))
      .catch(() => setOk(false))
  }, [])
  if (ok === null) return <Tag>服务连接中…</Tag>
  return ok ? <Tag color="green">服务在线</Tag> : <Tag color="red">服务未连接</Tag>
}

function ReadAccess({ children }: { children: ReactNode }) {
  const { status, user, canRead, loading, error, reload } = useAuth()
  if (loading) return <Spin tip="正在核验访问状态…"><div style={{ minHeight: 160 }} /></Spin>
  if (canRead) return <>{children}</>
  if (status?.configured && !user && !error) return <Navigate to="/login" replace />
  return <Alert type="warning" showIcon message={!status?.configured ? 'MDM 接入尚未就绪' : '当前身份无法访问质量分析页面'}
    description={error || '需要后端确认的查看权限；请联系平台负责人配置授权。'}
    action={<Space><Button onClick={reload}>重新检查</Button><Link to="/login">登录 MDM</Link></Space>} />
}

function LandingRoute() {
  const { loading, canPreview, canRead } = useAuth()
  if (loading) return <Spin />
  return <Navigate to={canPreview && !canRead ? '/imports' : '/release'} replace />
}

export default function App() {
  const loc = useLocation()
  const { user, status, canPreview, loading, logout } = useAuth()
  const [sidebarHost, setSidebarHost] = useState<HTMLDivElement | null>(null)
  const menu = [
    { key: '/release', label: <Link to="/release">放行趋势</Link> },
    { key: '/stability', label: <Link to="/stability">稳定性趋势</Link> },
    { key: '/similarity', label: <Link to="/similarity">相似性分析</Link> },
    { key: '/imports', disabled: !canPreview, label: <Link to="/imports">Excel 结构预览</Link> },
  ]
  return (
    <Layout className="qap-shell">
      <Header className="qap-header">
        <Link to="/release" className="qap-brand"><span className="qap-brand-mark">CMC</span><span><strong>质量分析看板</strong><small>Quality Analysis Dashboard</small></span></Link>
        <Space wrap>
          <HealthBadge />
          {status && !status.auth_required && !user && <Tag>本地只读开发模式</Tag>}
          {user ? <><span>{user.full_name || user.username}</span><Button onClick={() => void logout()}>退出</Button></> : <Link to="/login"><Button disabled={loading}>MDM 登录</Button></Link>}
        </Space>
      </Header>
      <SidebarHost.Provider value={sidebarHost}>
      <div className="qap-body">
        <aside className="qap-sidebar" aria-label="分析导航与筛选">
          <div className="qap-navigation-label">分析模块</div>
          <Menu mode="inline" selectedKeys={[loc.pathname]} items={menu} />
          <div ref={setSidebarHost} />
        </aside>
        <main className="qap-content">
          <Routes>
            <Route path="/" element={<LandingRoute />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/imports" element={<ImportPreviewPage />} />
            <Route path="/release" element={<ReadAccess><ReleaseTrendPage /></ReadAccess>} />
            <Route path="/stability" element={<ReadAccess><StabilityPage /></ReadAccess>} />
            <Route path="/similarity" element={<ReadAccess><Placeholder name="相似性分析" /></ReadAccess>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      </SidebarHost.Provider>
    </Layout>
  )
}
