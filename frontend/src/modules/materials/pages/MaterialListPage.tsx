import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { materialsApi } from '@/api/materials';
import type { MaterialBrief } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  MATERIAL_GRADE_OPTIONS,
  MATERIAL_STATUS_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function MaterialListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    material_type?: string;
    status?: string;
    grade?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['materials', page, pageSize, filters],
    queryFn: () =>
      materialsApi.list({ page, page_size: pageSize, ...filters }),
  });

  const items: MaterialBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '物料编码',
      dataIndex: 'material_code',
      key: 'material_code',
      width: 160,
      render: (code: string) => <EntityCodeLink type="material" code={code} />,
    },
    {
      title: '名称',
      dataIndex: 'material_name',
      key: 'material_name',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'material_type',
      key: 'material_type',
      width: 110,
      render: (t: string) => {
        const def = MATERIAL_TYPE_OPTIONS.find((o) => o.value === t);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? t}</Tag>;
      },
    },
    {
      title: '等级',
      dataIndex: 'grade',
      key: 'grade',
      width: 130,
      render: (g: string | null) => {
        if (!g) return '—';
        const def = MATERIAL_GRADE_OPTIONS.find((o) => o.value === g);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? g}</Tag>;
      },
    },
    {
      title: '物理形态',
      dataIndex: 'physical_form',
      key: 'physical_form',
      width: 110,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '关联物质',
      dataIndex: 'substance_code',
      key: 'substance_code',
      width: 140,
      render: (v: string | null) =>
        v ? <EntityCodeLink type="substance" code={v} /> : '—',
    },
    {
      title: '来源',
      dataIndex: 'source_name',
      key: 'source_name',
      width: 130,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => <StatusBadge type="material" status={s} />,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 130,
      render: (v: string) => <TimeDisplay value={v} />,
    },
  ];

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '物料' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              物料（Materials）
            </Title>
            <Text type="secondary">候选物 / 参比品 / 缓冲液等开发用物料登记，共 {total} 条</Text>
          </div>
          <PermissionGuard permission="material:create">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/materials/new')}
            >
              新建物料
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索 MAT-编码 / 名称 / 来源..."
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 320 }}
            value={pendingQ}
            onChange={(e) => setPendingQ(e.target.value)}
            onPressEnter={() => {
              setPage(1);
              setFilters((f) => ({ ...f, q: pendingQ || undefined }));
            }}
          />
          <Select
            placeholder="物料类型"
            allowClear
            style={{ width: 140 }}
            value={filters.material_type}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, material_type: v }));
            }}
            options={MATERIAL_TYPE_OPTIONS}
          />
          <Select
            placeholder="等级"
            allowClear
            style={{ width: 180 }}
            value={filters.grade}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, grade: v }));
            }}
            options={MATERIAL_GRADE_OPTIONS}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 130 }}
            value={filters.status}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, status: v }));
            }}
            options={MATERIAL_STATUS_OPTIONS}
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
        <Table<MaterialBrief>
          columns={columns}
          dataSource={items}
          rowKey="material_code"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: [10, 20, 50, 100],
            onChange: (p, size) => {
              setPage(p);
              setPageSize(size);
            },
          }}
          scroll={{ x: 1500 }}
        />
      </Card>
    </div>
  );
}
