import {
  AppstoreOutlined,
  AuditOutlined,
  BarcodeOutlined,
  CalculatorOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DotChartOutlined,
  ExperimentOutlined,
  LineChartOutlined,
} from '@ant-design/icons'
import { Tag } from 'antd'
import type { ReactNode } from 'react'

import type { HubApp } from '@/config/apps'

// 图标名 → 图标组件。注册表里 icon 字段填这里的 key；没有的回退到 appstore。
const ICONS: Record<string, ReactNode> = {
  database: <DatabaseOutlined />,
  experiment: <ExperimentOutlined />,
  barcode: <BarcodeOutlined />,
  'line-chart': <LineChartOutlined />,
  dashboard: <DashboardOutlined />,
  calculator: <CalculatorOutlined />,
  'dot-chart': <DotChartOutlined />,
  audit: <AuditOutlined />,
}

export default function AppTile({ app }: { app: HubApp }) {
  const planned = app.status === 'planned'
  const body = (
    <>
      <div className="tile-icon" style={{ background: planned ? '#bfbfbf' : app.color }}>
        {ICONS[app.icon] ?? <AppstoreOutlined />}
      </div>
      <div className="tile-name">{app.name}</div>
      {planned && (
        <Tag color="default" className="tile-tag" style={{ marginInlineEnd: 0 }}>
          建设中
        </Tag>
      )}
      {!planned && app.badge && (
        <Tag color="gold" className="tile-tag" style={{ marginInlineEnd: 0, fontWeight: 600 }}>
          {app.badge}
        </Tag>
      )}
      <div className="tile-desc" title={app.description}>
        {app.description}
      </div>
    </>
  )

  // 子系统是独立应用，用 <a href> 而不是前端路由；同源下令牌自动共享。
  // 在新标签页打开（负责人 2026-08-17 要求）：门户页保持不动，方便来回切换。
  if (planned) {
    return (
      <div className="tile tile-disabled" aria-disabled>
        {body}
      </div>
    )
  }
  return (
    <a className={`tile${app.tileTheme ? ` tile-${app.tileTheme}` : ''}`} href={app.path} target="_blank" rel="noopener">
      {body}
    </a>
  )
}
