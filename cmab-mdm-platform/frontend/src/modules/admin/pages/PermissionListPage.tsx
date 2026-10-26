import { useMemo } from 'react';
import {
  Breadcrumb,
  Card,
  Input,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import { useState } from 'react';
import { SafetyOutlined, SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { adminPermissionsApi } from '@/api/admin';
import type { PermissionItem } from '@/api/types';
import { AdminTabs } from '../components/AdminTabs';

const { Title, Text } = Typography;

const RESOURCE_COLORS: Record<string, string> = {
  substance: 'magenta',
  project: 'blue',
  asset: 'purple',
  material: 'cyan',
  audit: 'orange',
  user: 'volcano',
  role: 'red',
};

export function PermissionListPage() {
  const [search, setSearch] = useState('');

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['admin-permissions'],
    queryFn: () => adminPermissionsApi.list(),
  });

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (p) =>
        p.permission_code.toLowerCase().includes(q) ||
        p.resource.toLowerCase().includes(q) ||
        (p.description ?? '').toLowerCase().includes(q),
    );
  }, [items, search]);

  const columns = [
    {
      title: '权限码',
      dataIndex: 'permission_code',
      key: 'permission_code',
      width: 200,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '资源',
      dataIndex: 'resource',
      key: 'resource',
      width: 130,
      render: (v: string) => (
        <Tag color={RESOURCE_COLORS[v] ?? 'default'}>{v}</Tag>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 110,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (v: string | null) => v ?? '—',
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '权限' }]}
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
              权限列表（只读）
            </Title>
            <Text type="secondary">
              共 {items.length} 个权限码。权限由系统定义，不能新增或修改，仅可分配给角色。
            </Text>
          </div>
        </div>
      </Card>

      <Card>
        <AdminTabs />
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="搜索权限码 / 资源 / 描述..."
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 320 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Space>
        <Table<PermissionItem>
          columns={columns}
          dataSource={filtered}
          rowKey="permission_code"
          loading={isLoading}
          pagination={{
            pageSize: 50,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 个权限`,
          }}
        />
      </Card>
    </div>
  );
}
