import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
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
  CATEGORY_OPTIONS,
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
    category?: string;
    status?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const categoryOptions = CATEGORY_OPTIONS;

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
      width: 140,
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
      width: 90,
      render: (t: string) => {
        const def = MATERIAL_TYPE_OPTIONS.find((o) => o.value === t);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? t}</Tag>;
      },
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '生产商',
      dataIndex: 'manufacturer',
      key: 'manufacturer',
      width: 120,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 60,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '关联物质',
      dataIndex: 'substance_code',
      key: 'substance_code',
      width: 130,
      render: (v: string | null) =>
        v ? <EntityCodeLink type="substance" code={v} /> : '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => <StatusBadge type="material" status={s} />,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 120,
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
            <Text type="secondary">试剂 / 耗材 / 标准品 / 色谱柱等全公司物料身份注册，共 {total} 条</Text>
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
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} sm={10} md={8}>
            <Input
              placeholder="搜索编码 / 名称 / 生产商 / 货号..."
              prefix={<SearchOutlined />}
              allowClear
              value={pendingQ}
              onChange={(e) => setPendingQ(e.target.value)}
              onPressEnter={() => {
                setPage(1);
                setFilters((f) => ({ ...f, q: pendingQ || undefined }));
              }}
            />
          </Col>
          <Col>
            <Select
              placeholder="物料类型"
              allowClear
              style={{ width: 110 }}
              value={filters.material_type}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, material_type: v }));
              }}
              options={MATERIAL_TYPE_OPTIONS}
            />
          </Col>
          <Col>
            <Select
              placeholder="分类"
              allowClear
              style={{ width: 150 }}
              value={filters.category}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, category: v }));
              }}
              options={categoryOptions}
            />
          </Col>
          <Col>
            <Select
              placeholder="状态"
              allowClear
              style={{ width: 100 }}
              value={filters.status}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, status: v }));
              }}
              options={MATERIAL_STATUS_OPTIONS}
            />
          </Col>
          <Col>
            <Button
              onClick={() => {
                setPendingQ('');
                setFilters({});
                setPage(1);
              }}
            >
              重置
            </Button>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
              刷新
            </Button>
          </Col>
        </Row>
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
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  );
}
