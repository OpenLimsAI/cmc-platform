import { useState } from 'react';
import {
  Card,
  Table,
  Input,
  Select,
  Button,
  Space,
  Typography,
  Breadcrumb,
} from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { substancesApi } from '@/api/substances';
import type { SubstanceBrief } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { SubstanceTypeTag } from '@/shared/components/SubstanceTypeTag';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PermissionGuard } from '@/shared/components/PermissionGuard';

const { Title, Text } = Typography;

export function SubstanceListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    substance_type?: string;
    status?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['substances', page, pageSize, filters],
    queryFn: () =>
      substancesApi.list({
        page,
        page_size: pageSize,
        ...filters,
      }),
  });

  const items: SubstanceBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '物质编码',
      dataIndex: 'substance_code',
      key: 'substance_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="substance" code={code} />,
    },
    {
      title: '类型',
      dataIndex: 'substance_type',
      key: 'substance_type',
      width: 90,
      render: (t: string) => <SubstanceTypeTag type={t} />,
    },
    { title: '内部代号', dataIndex: 'internal_code', key: 'internal_code', width: 120 },
    {
      title: '首选名称',
      dataIndex: 'preferred_name',
      key: 'preferred_name',
      ellipsis: true,
    },
    { title: '靶点', dataIndex: 'target', key: 'target', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => <StatusBadge type="substance" status={s} />,
    },
    {
      title: '保密',
      dataIndex: 'confidentiality',
      key: 'confidentiality',
      width: 80,
      render: (c: string) => (c === 'restricted' ? '🔒 受限' : c === 'public' ? '公开' : '内部'),
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
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '物质' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              物质（Substances）
            </Title>
            <Text type="secondary">公司全部物质数据，共 {total} 条</Text>
          </div>
          <PermissionGuard permission="substance:create">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/substances/new')}
            >
              新建物质
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索编码、名称、INN..."
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
            placeholder="类型"
            allowClear
            style={{ width: 140 }}
            value={filters.substance_type}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, substance_type: v }));
            }}
            options={[
              { value: 'mab', label: '单抗 (mAb)' },
              { value: 'bispecific', label: '双抗' },
              { value: 'adc', label: 'ADC' },
              { value: 'fusion', label: '融合蛋白' },
              { value: 'small_molecule', label: '小分子' },
            ]}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 140 }}
            value={filters.status}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, status: v }));
            }}
            options={[
              { value: 'draft', label: '草稿' },
              { value: 'registered', label: '已注册' },
              { value: 'active', label: '活跃' },
              { value: 'restricted', label: '受限' },
              { value: 'deprecated', label: '已弃用' },
            ]}
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
          <Button
            icon={<ReloadOutlined />}
            onClick={() => refetch()}
          >
            刷新
          </Button>
        </Space>
      </Card>

      <Card>
        <Table<SubstanceBrief>
          columns={columns}
          dataSource={items}
          rowKey="substance_code"
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
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  );
}
