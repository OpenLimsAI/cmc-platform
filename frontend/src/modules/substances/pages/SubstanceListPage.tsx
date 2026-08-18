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
  Drawer,
  Form,
} from 'antd';
import { FilterOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
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
    target?: string;
    confidentiality?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');
  const [moreFiltersOpen, setMoreFiltersOpen] = useState(false);

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
    { title: '靶点', dataIndex: 'target', key: 'target', width: 140, ellipsis: true, render: (v: string | null) => v || '—' },
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
      // UI6（V1.1 §6.1 行 420-426）：关联项目计数
      title: '关联项目',
      dataIndex: 'project_count',
      key: 'project_count',
      width: 90,
      align: 'center' as const,
      render: (n: number) => (n > 0 ? n : '—'),
    },
    {
      title: '关联资产',
      dataIndex: 'asset_count',
      key: 'asset_count',
      width: 90,
      align: 'center' as const,
      render: (n: number) => (n > 0 ? n : '—'),
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
          {/* UI5（V1.1 §6.1.1 行 545）：靶点是常用筛选项 */}
          <Input
            placeholder="靶点（基因/名称/UniProt/CD 号）"
            allowClear
            style={{ width: 180 }}
            value={filters.target ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, target: e.target.value || undefined }))
            }
            onPressEnter={() => setPage(1)}
          />
          <Button icon={<FilterOutlined />} onClick={() => setMoreFiltersOpen(true)}>
            更多筛选
          </Button>
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

      {/* UI5（V1.1 §6.1.1 行 545）：「更多筛选」抽屉
          常用筛选放主区，深度筛选放抽屉；保密 / 是否专有 已接入 Batch F 后端，
          表达系统 / 创建人 / 日期范围 需要 SubstanceFilter 扩展（Phase 4 物料域时一起加）*/}
      <Drawer
        title="更多筛选"
        open={moreFiltersOpen}
        onClose={() => setMoreFiltersOpen(false)}
        width={360}
      >
        <Form layout="vertical">
          <Form.Item label="保密等级">
            <Select
              placeholder="选择保密等级"
              allowClear
              value={filters.confidentiality}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, confidentiality: v }));
              }}
              options={[
                { value: 'public', label: '公开' },
                { value: 'internal', label: '内部' },
                { value: 'restricted', label: '受限' },
              ]}
            />
          </Form.Item>
          <Form.Item label="表达系统 / 创建人 / 日期范围">
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Phase 4 SubstanceFilter 扩展时接入（V1.1 §6.1.1 行 545）
            </Typography.Text>
          </Form.Item>
          <Space>
            <Button
              onClick={() => {
                setFilters((f) => ({ ...f, confidentiality: undefined }));
                setMoreFiltersOpen(false);
              }}
            >
              清空抽屉项
            </Button>
            <Button type="primary" onClick={() => setMoreFiltersOpen(false)}>
              完成
            </Button>
          </Space>
        </Form>
      </Drawer>

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
