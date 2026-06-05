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
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { equipmentsApi, type EquipmentBrief } from '@/api/equipments';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  EQUIPMENT_CATEGORY_OPTIONS,
  EQUIPMENT_STATUS_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function EquipmentListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    category?: string;
    status?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['equipments', page, pageSize, filters],
    queryFn: () =>
      equipmentsApi.list({ page, page_size: pageSize, ...filters }),
  });

  const items: EquipmentBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '设备ID',
      dataIndex: 'equipment_code',
      key: 'equipment_code',
      width: 150,
      render: (code: string) => (
        <Link to={`/equipments/${encodeURIComponent(code)}`}>{code}</Link>
      ),
    },
    {
      title: '设备编号',
      dataIndex: 'equipment_no',
      key: 'equipment_no',
      width: 130,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '名称',
      dataIndex: 'equipment_name',
      key: 'equipment_name',
      ellipsis: true,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 200,
      render: (c: string) => {
        const def = EQUIPMENT_CATEGORY_OPTIONS.find((o) => o.value === c);
        return (
          <Tag
            color={def?.color ?? 'default'}
            style={{
              maxWidth: '100%',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {def?.label ?? c}
          </Tag>
        );
      },
    },
    {
      title: '型号',
      dataIndex: 'model',
      key: 'model',
      width: 160,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '生产商',
      dataIndex: 'manufacturer',
      key: 'manufacturer',
      width: 130,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '序列号',
      dataIndex: 'serial_no',
      key: 'serial_no',
      width: 140,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => {
        const def = EQUIPMENT_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
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
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '设备' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              设备（Equipments）
            </Title>
            <Text type="secondary">
              全公司仪器设备身份注册（主数据）；日常校验/维护/维修在 CMC LabOps Portal 操作，共 {total} 条
            </Text>
          </div>
          <PermissionGuard permission="equipment:create">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/equipments/new')}
            >
              新建设备
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} sm={10} md={8}>
            <Input
              placeholder="搜索设备ID / 设备编号 / 固资编号 / 名称 / 型号 / 生产商 / 序列号（多关键词空格分隔）"
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
              placeholder="分类"
              allowClear
              style={{ width: 120 }}
              value={filters.category}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, category: v }));
              }}
              options={EQUIPMENT_CATEGORY_OPTIONS}
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
              options={EQUIPMENT_STATUS_OPTIONS}
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
        <Table<EquipmentBrief>
          columns={columns}
          dataSource={items}
          rowKey="equipment_code"
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
