import { useEffect, useMemo, useState } from 'react';
import { Badge, Layout, Menu, Tooltip, Typography, theme } from 'antd';
import {
  DashboardOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  GoldOutlined,
  InboxOutlined,
  AuditOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { MicroscopeIcon } from '@/shared/components/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/api/client';
import { APP_VERSION } from '@/shared/version';

const { Sider } = Layout;

interface MenuItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  permission?: string;
}

const MENU_ITEMS: MenuItem[] = [
  { key: 'dashboard', label: '仪表盘', icon: <DashboardOutlined />, path: '/dashboard' },
  {
    key: 'substances',
    label: '物质',
    icon: <ExperimentOutlined />,
    path: '/substances',
    permission: 'substance:read',
  },
  {
    key: 'projects',
    label: '项目',
    icon: <FolderOpenOutlined />,
    path: '/projects',
    permission: 'project:read',
  },
  {
    key: 'assets',
    label: '资产',
    icon: <GoldOutlined />,
    path: '/assets',
    permission: 'asset:read',
  },
  {
    key: 'materials',
    label: '物料',
    icon: <InboxOutlined />,
    path: '/materials',
    permission: 'material:read',
  },
  {
    key: 'equipments',
    label: '设备',
    icon: <MicroscopeIcon />,
    path: '/equipments',
    permission: 'equipment:read',
  },
  {
    key: 'audit',
    label: '审计',
    icon: <AuditOutlined />,
    path: '/audit/logs',
    permission: 'audit:read',
  },
  {
    key: 'admin',
    label: '系统管理',
    icon: <SettingOutlined />,
    path: '/admin/users',
    permission: 'user:manage',
  },
];

type HealthStatus = 'checking' | 'ok' | 'down';

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const { token } = theme.useToken();

  // UI1（V1.1 §3.3）：Sidebar 底部健康检查绿点
  // 后端在 /api/v1/health 暴露 alias（main.py），走 axios api baseURL 自动拼到 /api/v1/health
  const [health, setHealth] = useState<HealthStatus>('checking');
  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        await api.get('/health', { timeout: 3000 });
        if (!cancelled) setHealth('ok');
      } catch {
        if (!cancelled) setHealth('down');
      }
    };
    probe();
    const t = setInterval(probe, 30000); // 30s 一次
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const items = useMemo(
    () =>
      MENU_ITEMS.filter((m) => !m.permission || isAdmin || hasPermission(m.permission)).map((m) => ({
        key: m.path,
        icon: m.icon,
        label: m.label,
      })),
    [hasPermission, isAdmin]
  );

  // 按顶层路径段匹配所属模块：菜单 key 是具体页(如 /admin/users)，
  // 但 /admin/roles、/audit/signatures 等子页也应高亮到对应模块。
  // 各菜单顶层段唯一(dashboard/substances/.../audit/admin)，故按第一段归属即可。
  const currentTop = location.pathname.split('/')[1] ?? '';
  const selectedKey =
    items.find((i) => (i.key as string).split('/')[1] === currentTop)?.key ?? '/dashboard';

  const healthBadge =
    health === 'ok' ? 'success' : health === 'down' ? 'error' : 'processing';
  const healthLabel =
    health === 'ok' ? '后端正常' : health === 'down' ? '后端不可用' : '健康检查中…';

  return (
    <Sider
      width={220}
      style={{
        background: '#fff',
        borderRight: `1px solid ${token.colorBorderSecondary}`,
        display: 'flex',
        flexDirection: 'column',
        height: '100%', // 填满行高，固定不随内容区滚动
      }}
      breakpoint="lg"
      collapsedWidth={64}
    >
      <Menu
        mode="inline"
        selectedKeys={[selectedKey as string]}
        items={items}
        style={{ borderRight: 0, paddingTop: 8, flex: 1, overflowY: 'auto' }}
        onClick={({ key }) => navigate(key as string)}
      />
      <div
        style={{
          padding: '8px 12px',
          borderTop: '1px solid #f0f0f0',
          fontSize: 12,
          color: '#8c8c8c',
        }}
      >
        <div style={{ marginBottom: 4 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {APP_VERSION}
          </Typography.Text>
        </div>
        <Tooltip title={healthLabel}>
          <Badge status={healthBadge} text={<span style={{ fontSize: 12 }}>{healthLabel}</span>} />
        </Tooltip>
      </div>
    </Sider>
  );
}
