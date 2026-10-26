import { Tabs } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

const TAB_ITEMS = [
  { key: '/admin/users', label: '用户' },
  { key: '/admin/roles', label: '角色' },
  { key: '/admin/permissions', label: '权限' },
  { key: '/admin/audit-logs', label: '审计日志' },
  { key: '/admin/signatures', label: '电子签名' },
  { key: '/admin/session-policy', label: '会话策略' },
  { key: '/admin/dept-admin-policy', label: '部门管理员' },
];

export function AdminTabs() {
  const location = useLocation();
  const navigate = useNavigate();
  // 部门管理员（DEPT_ADMIN）只有「用户」一页；其余页签不渲染（后端同样 403）
  const deptScoped = useAuthStore((s) => s.userAdminScope === 'department');
  const items = deptScoped ? TAB_ITEMS.filter((t) => t.key === '/admin/users') : TAB_ITEMS;

  const activeKey =
    items.find((t) => location.pathname.startsWith(t.key))?.key ?? '/admin/users';

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => navigate(key)}
      items={items}
      style={{ marginBottom: 16 }}
    />
  );
}
