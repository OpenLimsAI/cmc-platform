import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Dropdown,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  EditOutlined,
  KeyOutlined,
  LockOutlined,
  MoreOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyOutlined,
  SearchOutlined,
  UnlockOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminUsersApi } from '@/api/admin';
import type {
  ResetPasswordResult,
  UserDetail,
  UserListItem,
  UserStatus,
} from '@/api/types';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { useAuthStore } from '@/stores/authStore';
import {
  PROTECTED_ROLES,
  ROLE_COLORS,
  ROLE_LABELS,
  USER_STATUS_COLORS,
  USER_STATUS_LABELS,
  USER_STATUS_OPTIONS,
} from '../constants';
import { useRoleOptions } from '../useRoleOptions';
import { AdminTabs } from '../components/AdminTabs';
import { UserFormDrawer } from '../components/UserFormDrawer';
import { UserRoleAssignModal } from '../components/UserRoleAssignModal';
import { ResetPasswordResultModal } from '../components/ResetPasswordResultModal';

const { Title, Text } = Typography;

export function UserListPage() {
  const queryClient = useQueryClient();
  const currentUsername = useAuthStore((s) => s.user?.username);
  // 部门管理员（DEPT_ADMIN）：后端只返回本部门用户；这里只渲染允许的操作
  // （分配白名单角色、锁定/解锁），新建/编辑/重置密码按钮不渲染，而不是点了报错。
  const deptScoped = useAuthStore((s) => s.userAdminScope === 'department');
  const myDepartment = useAuthStore((s) => s.user?.department);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    role_code?: string;
    status?: UserStatus;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  // Drawer / Modal 状态
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingUser, setEditingUser] = useState<UserDetail | null>(null);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [resetResult, setResetResult] = useState<ResetPasswordResult | null>(null);

  // M5.2：角色筛选下拉动态拉取
  const { options: roleFilterOptions } = useRoleOptions();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-users', page, pageSize, filters],
    queryFn: () =>
      adminUsersApi.list({ page, page_size: pageSize, ...filters }),
  });

  const items: UserListItem[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin-users'] });

  const lockMutation = useMutation({
    mutationFn: (username: string) => adminUsersApi.lock(username),
    onSuccess: (_, username) => {
      message.success(`已锁定 ${username}`);
      invalidate();
    },
  });

  const unlockMutation = useMutation({
    mutationFn: (username: string) => adminUsersApi.unlock(username),
    onSuccess: (_, username) => {
      message.success(`已解锁 ${username}`);
      invalidate();
    },
  });

  const resetMutation = useMutation({
    mutationFn: (username: string) => adminUsersApi.resetPassword(username),
    onSuccess: (result) => {
      setResetResult(result);
      invalidate();
    },
  });

  const openCreate = () => {
    setDrawerMode('create');
    setEditingUser(null);
    setDrawerOpen(true);
  };

  const openEdit = async (username: string) => {
    const detail = await adminUsersApi.get(username);
    setEditingUser(detail);
    setDrawerMode('edit');
    setDrawerOpen(true);
  };

  const openRoleAssign = async (username: string) => {
    const detail = await adminUsersApi.get(username);
    setEditingUser(detail);
    setRoleModalOpen(true);
  };

  const confirmLock = (username: string) => {
    Modal.confirm({
      title: `锁定用户 ${username}？`,
      content:
        '锁定后该用户无法登录，所有活跃会话立即失效。审计记录保留完整。',
      okText: '锁定',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => lockMutation.mutateAsync(username),
    });
  };

  const confirmReset = (username: string) => {
    Modal.confirm({
      title: `重置 ${username} 的密码？`,
      content:
        '重置后系统生成 16 位临时密码，请通过安全渠道告知用户。用户首次登录将被强制改密。',
      okText: '重置',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => resetMutation.mutateAsync(username),
    });
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 140,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    { title: '姓名', dataIndex: 'full_name', key: 'full_name', width: 130 },
    { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
    { title: '部门', dataIndex: 'department', key: 'department', width: 110 },
    { title: '职位', dataIndex: 'title', key: 'title', width: 130 },
    {
      title: '角色',
      key: 'roles',
      width: 280,
      render: (_: unknown, r: UserListItem) => (
        <>
          {r.roles.map((role) => (
            <Tag key={role.role_code} color={ROLE_COLORS[role.role_code]}>
              {ROLE_LABELS[role.role_code] ?? role.role_name}
            </Tag>
          ))}
        </>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: UserStatus) => (
        <Tag color={USER_STATUS_COLORS[s] ?? 'default'}>
          {USER_STATUS_LABELS[s] ?? s}
        </Tag>
      ),
    },
    {
      title: '最近登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 150,
      render: (v: string | null | undefined) =>
        v ? <TimeDisplay value={v} /> : <Text type="secondary">—</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, r: UserListItem) => {
        const isSelf = r.username === currentUsername;
        // 部门管理员不能锁定/解锁持有 SYS_ADMIN / DEPT_ADMIN 的账号（后端同样拦）
        const lockAllowed =
          !deptScoped || !r.roles.some((role) => PROTECTED_ROLES.has(role.role_code));
        const lockItems = lockAllowed
          ? r.status === 'locked'
            ? [
                {
                  key: 'unlock',
                  icon: <UnlockOutlined />,
                  label: '解锁',
                  onClick: () => unlockMutation.mutate(r.username),
                },
              ]
            : [
                {
                  key: 'lock',
                  icon: <LockOutlined />,
                  label: '锁定',
                  disabled: isSelf,
                  onClick: () => confirmLock(r.username),
                },
              ]
          : [];
        const menuItems = deptScoped
          ? [
              {
                key: 'roles',
                icon: <UserSwitchOutlined />,
                label: '分配角色',
                onClick: () => openRoleAssign(r.username),
              },
              ...(lockItems.length ? [{ type: 'divider' as const }, ...lockItems] : []),
            ]
          : [
              {
                key: 'edit',
                icon: <EditOutlined />,
                label: '编辑信息',
                onClick: () => openEdit(r.username),
              },
              {
                key: 'roles',
                icon: <UserSwitchOutlined />,
                label: '分配角色',
                onClick: () => openRoleAssign(r.username),
              },
              { type: 'divider' as const },
              ...lockItems,
              {
                key: 'reset',
                icon: <KeyOutlined />,
                label: '重置密码',
                disabled: isSelf,
                danger: true,
                onClick: () => confirmReset(r.username),
              },
            ];
        return (
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button type="text" icon={<MoreOutlined />} />
          </Dropdown>
        );
      },
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '用户' }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <Title level={3} style={{ margin: 0 }}>
              <SafetyOutlined style={{ marginRight: 8 }} />
              {deptScoped ? `本部门用户管理（${myDepartment ?? '未填写部门'}）` : '用户管理'}
            </Title>
            <Text type="secondary">
              {deptScoped
                ? `只显示与你同部门的用户，共 ${total} 人；可分配验证部等允许下放的角色、锁定/解锁。新建用户、改资料、重置密码请联系系统管理员。`
                : `管理平台账户、角色与登录状态，共 ${total} 个用户`}
            </Text>
          </div>
          {!deptScoped && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建用户
            </Button>
          )}
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <AdminTabs />
        <Space wrap>
          <Input
            placeholder="搜索 用户名 / 姓名 / 邮箱..."
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 280 }}
            value={pendingQ}
            onChange={(e) => setPendingQ(e.target.value)}
            onPressEnter={() => {
              setPage(1);
              setFilters((f) => ({ ...f, q: pendingQ || undefined }));
            }}
          />
          <Select
            placeholder="角色"
            allowClear
            style={{ width: 180 }}
            value={filters.role_code}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, role_code: v }));
            }}
            options={roleFilterOptions}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 130 }}
            value={filters.status}
            onChange={(v: UserStatus | undefined) => {
              setPage(1);
              setFilters((f) => ({ ...f, status: v }));
            }}
            options={USER_STATUS_OPTIONS}
          />
          <Button
            onClick={() => {
              setPendingQ('');
              setFilters({});
              setPage(1);
            }}
          >
            重置
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
            刷新
          </Button>
        </Space>
      </Card>

      <Card>
        <Table<UserListItem>
          columns={columns}
          dataSource={items}
          rowKey="username"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 个用户`,
            pageSizeOptions: [10, 20, 50, 100],
            onChange: (p, size) => {
              setPage(p);
              setPageSize(size);
            },
          }}
          scroll={{ x: 1500 }}
        />
      </Card>

      <UserFormDrawer
        open={drawerOpen}
        mode={drawerMode}
        user={editingUser}
        onClose={() => setDrawerOpen(false)}
        onSaved={() => {
          message.success(drawerMode === 'create' ? '用户已创建' : '用户已更新');
          invalidate();
        }}
      />

      <UserRoleAssignModal
        open={roleModalOpen}
        user={editingUser}
        deptScoped={deptScoped}
        onClose={() => setRoleModalOpen(false)}
        onSaved={() => {
          message.success('角色已更新');
          invalidate();
        }}
      />

      <ResetPasswordResultModal
        open={resetResult !== null}
        result={resetResult}
        onClose={() => setResetResult(null)}
      />
    </div>
  );
}
