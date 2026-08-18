import { useState } from 'react';
import { Breadcrumb, Button, Card, Col, Input, Row, Select, Table, Tag, Typography } from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { targetsApi, type TargetBrief } from '@/api/targets';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { COMMON_LOCATIONS, COMMON_MF_KEYWORDS, ENTRY_TYPE_OPTIONS, TARGET_STATUS_OPTIONS } from '../constants';

const { Title, Text } = Typography;

export function TargetListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    keyword?: string;
    location?: string;
    entry_type?: string;
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
      title: 'CD 号',
      dataIndex: 'cd_antigen_names',
      key: 'cd_antigen_names',
      width: 100,
      render: (v: string[] | null) => (v?.length ? v.map((c) => <Tag key={c} color="geekblue">{c}</Tag>) : '—'),
    },
    {
      title: '分子功能（UniProt 关键词）',
      dataIndex: 'keywords',
      key: 'keywords',
      width: 220,
      render: (kws: TargetBrief['keywords']) => {
        const mf = (kws ?? []).filter((k) => k.category === 'Molecular function');
        if (!mf.length) return '—';
        return (
          <>
            {mf.slice(0, 3).map((k) => (
              <Tag key={k.id ?? k.name} color="blue">{k.name}</Tag>
            ))}
            {mf.length > 3 && <Tag>+{mf.length - 3}</Tag>}
          </>
        );
      },
    },
    {
      title: '亚细胞定位',
      dataIndex: 'subcellular_locations',
      key: 'subcellular_locations',
      width: 180,
      ellipsis: true,
      render: (sls: TargetBrief['subcellular_locations']) => {
        const uniq = [...new Set((sls ?? []).map((sl) => sl.location))];
        if (!uniq.length) return '—';
        return (
          <>
            {uniq.slice(0, 2).map((l) => (
              <Tag key={l} color="green">{l}</Tag>
            ))}
            {uniq.length > 2 && <Tag>+{uniq.length - 2}</Tag>}
          </>
        );
      },
    },
    {
      title: '条目',
      dataIndex: 'entry_type',
      key: 'entry_type',
      width: 90,
      render: (v: string | null) =>
        v ? <Tag color={v.includes('unreviewed') ? 'orange' : 'default'}>{v.includes('unreviewed') ? 'TrEMBL' : 'Swiss-Prot'}</Tag> : '—',
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
              抗体分子的作用靶点主数据，字段按 UniProt 标准自动维护（锚点 accession）；分子本身在「物质」域，共 {total} 条
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
              placeholder="搜索编码 / 名称 / UniProt / 基因 / CD 号 / 别名（空格分隔多词）"
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
              placeholder="分子功能关键词"
              allowClear
              showSearch
              mode="tags"
              maxCount={1}
              style={{ width: 180 }}
              value={filters.keyword ? [filters.keyword] : []}
              onChange={(v: string[]) => {
                setPage(1);
                setFilters((f) => ({ ...f, keyword: v?.[0] || undefined }));
              }}
              options={COMMON_MF_KEYWORDS.map((k) => ({ value: k, label: k }))}
            />
          </Col>
          <Col>
            <Select
              placeholder="亚细胞定位"
              allowClear
              showSearch
              mode="tags"
              maxCount={1}
              style={{ width: 170 }}
              value={filters.location ? [filters.location] : []}
              onChange={(v: string[]) => {
                setPage(1);
                setFilters((f) => ({ ...f, location: v?.[0] || undefined }));
              }}
              options={COMMON_LOCATIONS.map((k) => ({ value: k, label: k }))}
            />
          </Col>
          <Col>
            <Select
              placeholder="条目类型"
              allowClear
              style={{ width: 170 }}
              value={filters.entry_type}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, entry_type: v }));
              }}
              options={ENTRY_TYPE_OPTIONS}
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
          scroll={{ x: 1300 }}
        />
      </Card>
    </div>
  );
}
