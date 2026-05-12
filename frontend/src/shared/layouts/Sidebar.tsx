import { useMemo } from 'react';
import { Layout, Menu, theme } from 'antd';
import {
  DashboardOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  GoldOutlined,
  InboxOutlined,
  AuditOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

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

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const { token } = theme.useToken();

  // 按权限过滤菜单
  const items = useMemo(
    () =>
      MENU_ITEMS.filter((m) => !m.permission || isAdmin || hasPermission(m.permission)).map((m) => ({
        key: m.path,
        icon: m.icon,
        label: m.label,
      })),
    [hasPermission, isAdmin]
  );

  // 当前激活：路径前缀匹配
  const selectedKey =
    items.find((i) => location.pathname.startsWith(i.key as string))?.key ?? '/dashboard';

  return (
    <Sider
      width={220}
      style={{
        background: '#fff',
        borderRight: `1px solid ${token.colorBorderSecondary}`,
      }}
      breakpoint="lg"
      collapsedWidth={64}
    >
      <Menu
        mode="inline"
        selectedKeys={[selectedKey as string]}
        items={items}
        style={{ borderRight: 0, paddingTop: 8 }}
        onClick={({ key }) => navigate(key as string)}
      />
    </Sider>
  );
}
