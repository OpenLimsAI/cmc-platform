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
import { projectsApi } from '@/api/projects';
import type { ProjectBrief } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  PROJECT_CONFIDENTIALITY_OPTIONS,
  PROJECT_PHASE_OPTIONS,
  PROJECT_PRIORITY_OPTIONS,
  PROJECT_STATUS_OPTIONS,
  PROJECT_TYPE_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function ProjectListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<{
    q?: string;
    project_type?: string;
    project_phase?: string;
    status?: string;
    priority?: string;
    program_name?: string;
    parent_project_id?: number;
    confidentiality?: string;
  }>({});
  const [pendingQ, setPendingQ] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['projects', page, pageSize, filters],
    queryFn: () =>
      projectsApi.list({
        page,
        page_size: pageSize,
        ...filters,
      }),
  });

  const items: ProjectBrief[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '项目编码',
      dataIndex: 'project_code',
      key: 'project_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="project" code={code} />,
    },
    {
      title: '项目名称',
      dataIndex: 'project_name',
      key: 'project_name',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'project_type',
      key: 'project_type',
      width: 110,
      render: (t: string) => PROJECT_TYPE_OPTIONS.find((o) => o.value === t)?.label ?? t,
    },
    {
      title: '阶段',
      dataIndex: 'project_phase',
      key: 'project_phase',
      width: 100,
      render: (p: string | null) =>
        p ? PROJECT_PHASE_OPTIONS.find((o) => o.value === p)?.label ?? p : '—',
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
      width: 120,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => <StatusBadge type="project" status={s} />,
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
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '项目' }]} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              项目（Projects）
            </Title>
            <Text type="secondary">公司全部项目登记，共 {total} 条</Text>
          </div>
          <PermissionGuard permission="project:create">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/projects/new')}
            >
              新建项目
            </Button>
          </PermissionGuard>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索编码、名称、适应症..."
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
            placeholder="项目类型"
            allowClear
            style={{ width: 160 }}
            value={filters.project_type}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, project_type: v }));
            }}
            options={PROJECT_TYPE_OPTIONS}
          />
          <Select
            placeholder="阶段"
            allowClear
            style={{ width: 140 }}
            value={filters.project_phase}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, project_phase: v }));
            }}
            options={PROJECT_PHASE_OPTIONS}
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
            options={PROJECT_STATUS_OPTIONS}
          />
          {/* UI10（V1.1 §9.2 / Batch F）：priority / program_name / parent_project_id / confidentiality */}
          <Select
            placeholder="优先级"
            allowClear
            style={{ width: 120 }}
            value={filters.priority}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, priority: v }));
            }}
            options={PROJECT_PRIORITY_OPTIONS}
          />
          <Select
            placeholder="保密"
            allowClear
            style={{ width: 110 }}
            value={filters.confidentiality}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, confidentiality: v }));
            }}
            options={PROJECT_CONFIDENTIALITY_OPTIONS}
          />
          <Input
            placeholder="项目群"
            allowClear
            style={{ width: 160 }}
            value={filters.program_name ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, program_name: e.target.value || undefined }))
            }
            onPressEnter={() => setPage(1)}
          />
          <Input
            placeholder="父项目 ID"
            allowClear
            type="number"
            style={{ width: 120 }}
            value={filters.parent_project_id ?? ''}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                parent_project_id: e.target.value ? Number(e.target.value) : undefined,
              }))
            }
            onPressEnter={() => setPage(1)}
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
        <Table<ProjectBrief>
          columns={columns}
          dataSource={items}
          rowKey="project_code"
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
