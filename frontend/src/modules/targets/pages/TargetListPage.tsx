import { useState } from 'react';
import { Breadcrumb, Button, Card, Col, Input, Row, Select, Table, Tag, Typography } from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { targetsApi, type TargetBrief } from '@/api/targets';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { TARGET_LOCATION_OPTIONS, TARGET_STATUS_OPTIONS, TARGET_TYPE_OPTIONS } from '../constants';

const { Title, Text } = Typography;

export function TargetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    target_type?: string;
    target_location?: string;
    status?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['targets', page, pageSize, filters],
    queryFn: () => targetsApi.list({ page, page_size: pageSize, ...filters }),
  });

  const items: TargetBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '靶点编码',
      dataIndex: 'target_code',
      key: 'target_code',
      width: 130,
      render: (code: string) => <Link to={`/targets/${encodeURIComponent(code)}`}>{code}</Link>,
    },
    { title: '名称', dataIndex: 'target_name', key: 'target_name', ellipsis: true },
    {
      title: 'UniProt',
      dataIndex: 'uniprot_id',
      key: 'uniprot_id',
      width: 110,
      render: (v: string | null) =>
        v ? (
          <a href={`https://www.uniprot.org/uniprotkb/${v}/entry`} target="_blank" rel="noreferrer">
            {v}
          </a>
        ) : (
          '—'
        ),
    },
    {
      title: '基因',
      dataIndex: 'gene_symbol',
      key: 'gene_symbol',
      width: 100,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '类型',
      dataIndex: 'target_type',
      key: 'target_type',
      width: 130,
      render: (t: string) => {
        const def = TARGET_TYPE_OPTIONS.find((o) => o.value === t);
        return <Tag color={def?.color}>{def?.label ?? t}</Tag>;
      },
    },
    {
      title: '定位',
      dataIndex: 'target_location',
      key: 'target_location',
      width: 100,
      render: (t: string) => {
        const def = TARGET_LOCATION_OPTIONS.find((o) => o.value === t);
        return <Tag color={def?.color}>{def?.label ?? t}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => {
        const def = TARGET_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color}>{def?.label ?? s}</Tag>;
      },
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
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '靶点' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              靶点（Targets）
            </Title>
            <Text type="secondary">
              抗体分子的作用靶点主数据，锚点 UniProt accession；分子本身在「物质」域，共 {total} 条
            </Text>
          </div>
          <PermissionGuard permission="target:create">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/targets/new')}>
              新建靶点
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} sm={10} md={8}>
            <Input
              placeholder="搜索编码 / 名称 / UniProt / 基因 / 别名（多关键词空格分隔）"
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
              placeholder="类型"
              allowClear
              style={{ width: 130 }}
              value={filters.target_type}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, target_type: v }));
              }}
              options={TARGET_TYPE_OPTIONS}
            />
          </Col>
          <Col>
            <Select
              placeholder="定位"
              allowClear
              style={{ width: 110 }}
              value={filters.target_location}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, target_location: v }));
              }}
              options={TARGET_LOCATION_OPTIONS}
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
              options={TARGET_STATUS_OPTIONS}
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
        <Table<TargetBrief>
          columns={columns}
          dataSource={items}
          rowKey="target_code"
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
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  );
}
