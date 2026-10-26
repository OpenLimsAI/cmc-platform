import { useState } from 'react';
import {
  Card,
  Table,
  Input,
  Select,
  Button,
  Space,
  Tag,
  Typography,
  Breadcrumb,
} from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { assetsApi } from '@/api/assets';
import type { AssetBrief } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  ASSET_PHASE_OPTIONS,
  ASSET_STATUS_OPTIONS,
  ASSET_TYPE_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function AssetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    asset_type?: string;
    current_phase?: string;
    status?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['assets', page, pageSize, filters],
    queryFn: () =>
      assetsApi.list({
        page,
        page_size: pageSize,
        ...filters,
      }),
  });

  const items: AssetBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '资产编码',
      dataIndex: 'asset_code',
      key: 'asset_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="asset" code={code} />,
    },
    {
      title: '内部名',
      dataIndex: 'internal_name',
      key: 'internal_name',
      ellipsis: true,
    },
    {
      title: '商品名',
      dataIndex: 'trade_name',
      key: 'trade_name',
      width: 140,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '类型',
      dataIndex: 'asset_type',
      key: 'asset_type',
      width: 100,
      render: (t: string) => ASSET_TYPE_OPTIONS.find((o) => o.value === t)?.label ?? t,
    },
    {
      title: '阶段',
      dataIndex: 'current_phase',
      key: 'current_phase',
      width: 100,
      render: (p: string) => {
        const def = ASSET_PHASE_OPTIONS.find((o) => o.value === p);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? p}</Tag>;
      },
    },
    {
      title: '治疗领域',
      dataIndex: 'therapeutic_area',
      key: 'therapeutic_area',
      width: 120,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => <StatusBadge type="asset" status={s} />,
    },
    {
      title: '商业化',
      dataIndex: 'is_commercial',
      key: 'is_commercial',
      width: 80,
      render: (v: boolean) => (v ? '✓' : '—'),
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
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '资产' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              资产（Assets）
            </Title>
            <Text type="secondary">公司全部开发资产登记，共 {total} 条</Text>
          </div>
          <PermissionGuard permission="asset:create">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/assets/new')}
            >
              新建资产
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索 AST-编码 / 内部名 / 商品名 / INN..."
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
            placeholder="资产类型"
            allowClear
            style={{ width: 140 }}
            value={filters.asset_type}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, asset_type: v }));
            }}
            options={ASSET_TYPE_OPTIONS}
          />
          <Select
            placeholder="阶段"
            allowClear
            style={{ width: 140 }}
            value={filters.current_phase}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, current_phase: v }));
            }}
            options={ASSET_PHASE_OPTIONS}
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
            options={ASSET_STATUS_OPTIONS}
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
        <Table<AssetBrief>
          columns={columns}
          dataSource={items}
          rowKey="asset_code"
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
          scroll={{ x: 1300 }}
        />
      </Card>
    </div>
  );
}
