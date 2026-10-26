import { useState } from 'react';
import { Breadcrumb, Button, Card, Col, Input, Row, Select, Table, Tag, Tooltip, Typography } from 'antd';
import { ColumnWidthOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { equipmentsApi, type EquipmentBrief } from '@/api/equipments';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { useResizableColumns } from '@/shared/components/useResizableColumns';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  EQUIPMENT_CATEGORY_OPTIONS,
  EQUIPMENT_MASTER_STATUS_OPTIONS,
  EQUIPMENT_STATUS_OPTIONS,
  criticalityDef,
} from '../constants';

const { Title, Text } = Typography;
// 在服务端先排序再分页；设备ID用于同部门、同编号时稳定排序。
const EQUIPMENT_LIST_SORT = 'department,equipment_no,equipment_code';

export function EquipmentListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    category?: string;
    status?: string;
    equipment_status?: string;
    department?: string;
    criticality?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['equipments', page, pageSize, filters, EQUIPMENT_LIST_SORT],
    queryFn: () =>
      equipmentsApi.list({ page, page_size: pageSize, ...filters, sort: EQUIPMENT_LIST_SORT }),
  });

  const items: EquipmentBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const baseColumns = [
    {
      title: '设备ID',
      dataIndex: 'equipment_code',
      key: 'equipment_code',
      width: 140,
      render: (code: string) => (
        <Link to={`/equipments/${encodeURIComponent(code)}`}>{code}</Link>
      ),
    },
    {
      title: '设备编号',
      dataIndex: 'equipment_no',
      key: 'equipment_no',
      width: 125,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      // 最关键的一列：默认给足宽度，放不下时鼠标悬停看全称（还可拖表头边缘自行调整）
      title: '名称',
      dataIndex: 'equipment_name',
      key: 'equipment_name',
      width: 280,
      ellipsis: { showTitle: true } as const,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 150,
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
      width: 140,
      ellipsis: true,
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
      title: '使用部门',
      dataIndex: 'department',
      key: 'department',
      width: 100,
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '存放位置',
      key: 'location',
      width: 160,
      ellipsis: true,
      render: (_: unknown, r: EquipmentBrief) =>
        [r.site, r.room].filter(Boolean).join(' · ') || '—',
    },
    {
      title: '分级',
      dataIndex: 'criticality',
      key: 'criticality',
      width: 90,
      render: (v: string | null) => {
        if (!v) return '—';
        const def = criticalityDef(v);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? v}</Tag>;
      },
    },
    {
      title: '主数据状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (s: string) => {
        const def = EQUIPMENT_MASTER_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
      },
    },
    {
      title: '设备状态',
      dataIndex: 'equipment_status',
      key: 'equipment_status',
      width: 100,
      render: (s: string) => {
        const def = EQUIPMENT_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 110,
      render: (v: string) => <TimeDisplay value={v} />,
    },
  ];

  // 列宽可拖拽调整，按登录人分别记在本机（见 shared/components/resizableColumns）
  const { columns, components, resetWidths, totalWidth, isCustomized } = useResizableColumns(
    'equipments',
    baseColumns,
  );

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
              全公司设备清单及设备状态由设备部维护；校准归计量专员、验证归验证部平台，共 {total} 条
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
              placeholder="搜索设备ID / 编号 / 名称 / 型号 / 生产商 / 序列号 / 部门 / 位置（多关键词空格分隔）"
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
              placeholder="主数据状态"
              allowClear
              style={{ width: 120 }}
              value={filters.status}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, status: v }));
              }}
              options={EQUIPMENT_MASTER_STATUS_OPTIONS}
            />
          </Col>
          <Col>
            <Select
              placeholder="设备状态"
              allowClear
              style={{ width: 110 }}
              value={filters.equipment_status}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, equipment_status: v }));
              }}
              options={EQUIPMENT_STATUS_OPTIONS}
            />
          </Col>
          <Col>
            <Select
              placeholder="分级"
              allowClear
              style={{ width: 110 }}
              value={filters.criticality}
              onChange={(v) => {
                setPage(1);
                setFilters((f) => ({ ...f, criticality: v }));
              }}
              options={[
                { value: 'A', label: 'A 级' },
                { value: 'B', label: 'B 级' },
                { value: 'C', label: 'C 级' },
                { value: '关键', label: '关键设备' },
                { value: '一般', label: '一般设备' },
              ]}
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
          {isCustomized && (
            <Col>
              <Tooltip title="把列宽恢复成系统默认（只影响你自己这台电脑）">
                <Button icon={<ColumnWidthOutlined />} onClick={resetWidths}>
                  恢复列宽
                </Button>
              </Tooltip>
            </Col>
          )}
        </Row>
      </Card>

      <Card>
        <Table<EquipmentBrief>
          columns={columns}
          components={components}
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
          scroll={{ x: Math.max(totalWidth, 1200) }}
        />
      </Card>
    </div>
  );
}
