import { Tabs } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';

const TAB_ITEMS = [
  { key: '/admin/users', label: '用户' },
  { key: '/admin/roles', label: '角色' },
  { key: '/admin/permissions', label: '权限' },
  { key: '/admin/audit-logs', label: '审计日志' },
  { key: '/admin/signatures', label: '电子签名' },
];

export function AdminTabs() {
  const location = useLocation();
  const navigate = useNavigate();

  const activeKey =
    TAB_ITEMS.find((t) => location.pathname.startsWith(t.key))?.key ?? '/admin/users';

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => navigate(key)}
      items={TAB_ITEMS}
      style={{ marginBottom: 16 }}
    />
  );
}
