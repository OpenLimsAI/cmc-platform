import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Modal,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminRolesApi } from '@/api/admin';
import type { RoleDetail, RoleListItem } from '@/api/types';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { AdminTabs } from '../components/AdminTabs';
import { RoleFormDrawer } from '../components/RoleFormDrawer';
import { ROLE_LABELS } from '../constants';

const { Title, Text } = Typography;

export function RoleListPage() {
  const queryClient = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingRole, setEditingRole] = useState<RoleDetail | null>(null);

  const { data: items = [], isLoading, refetch } = useQuery({
    queryKey: ['admin-roles'],
    queryFn: () => adminRolesApi.list(),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin-roles'] });

  const deleteMutation = useMutation({
    mutationFn: (role_code: string) => adminRolesApi.delete(role_code),
    onSuccess: (_, code) => {
      message.success(`已删除角色 ${code}`);
      invalidate();
    },
  });

  const openCreate = () => {
    setDrawerMode('create');
    setEditingRole(null);
    setDrawerOpen(true);
  };

  const openEdit = async (role_code: string) => {
    const detail = await adminRolesApi.get(role_code);
    setEditingRole(detail);
    setDrawerMode('edit');
    setDrawerOpen(true);
  };

  const confirmDelete = (role: RoleListItem) => {
    if (role.user_count > 0) {
      Modal.warning({
        title: `无法删除角色 ${role.role_code}`,
        content: `当前仍有 ${role.user_count} 个用户持有该角色，请先将这些用户改为其他角色后再删除。`,
      });
      return;
    }
    Modal.confirm({
      title: `删除角色 ${role.role_code}？`,
      content: '删除后该角色不再可用，已有用户的历史审计记录不受影响。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => deleteMutation.mutateAsync(role.role_code),
    });
  };

  const columns = [
    {
      title: '编码',
      dataIndex: 'role_code',
      key: 'role_code',
      width: 200,
      render: (code: string, r: RoleListItem) => (
        <Space>
          <Text strong>{code}</Text>
          {r.is_system ? (
            <Tag color="purple">系统</Tag>
          ) : (
            <Tag color="default">自定义</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '名称',
      dataIndex: 'role_name',
      key: 'role_name',
      width: 200,
      render: (name: string, r: RoleListItem) => ROLE_LABELS[r.role_code] ?? name,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '权限数',
      dataIndex: 'permission_count',
      key: 'permission_count',
      width: 90,
      align: 'right' as const,
    },
    {
      title: '用户数',
      dataIndex: 'user_count',
      key: 'user_count',
      width: 90,
      align: 'right' as const,
      render: (v: number) => (v > 0 ? <Tag color="blue">{v}</Tag> : <Text type="secondary">0</Text>),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 150,
      render: (v: string) => <TimeDisplay value={v} />,
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      fixed: 'right' as const,
      render: (_: unknown, r: RoleListItem) => {
        if (r.is_system) {
          return (
            <Tooltip title="系统内置角色不可修改或删除">
              <Button type="link" disabled icon={<EditOutlined />}>
                只读
              </Button>
            </Tooltip>
          );
        }
        return (
          <Space>
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => openEdit(r.role_code)}
            >
              编辑
            </Button>
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              onClick={() => confirmDelete(r)}
            >
              删除
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '角色' }]}
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
              角色管理
            </Title>
            <Text type="secondary">
              {items.filter((r) => r.is_system).length} 个系统角色（不可改/删） +{' '}
              {items.filter((r) => !r.is_system).length} 个自定义角色
            </Text>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建自定义角色
            </Button>
          </Space>
        </div>
      </Card>

      <Card>
        <AdminTabs />
        <Table<RoleListItem>
          columns={columns}
          dataSource={items}
          rowKey="role_code"
          loading={isLoading}
          pagination={false}
          scroll={{ x: 1100 }}
        />
      </Card>

      <RoleFormDrawer
        open={drawerOpen}
        mode={drawerMode}
        role={editingRole}
        onClose={() => setDrawerOpen(false)}
        onSaved={() => {
          message.success(drawerMode === 'create' ? '角色已创建' : '角色已更新');
          invalidate();
        }}
      />
    </div>
  );
}
