import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  DatePicker,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  AuditOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import { useMutation, useQuery } from '@tanstack/react-query';
import { adminAuditApi } from '@/api/admin';
import type { AuditLogItem, AuditLogQuery } from '@/api/types';
import { ChangesView } from '@/shared/components/AuditLogPanel';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { AdminTabs } from '../components/AdminTabs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const ACTION_COLOR: Record<string, string> = {
  CREATE: 'green',
  UPDATE: 'blue',
  DELETE: 'red',
  APPROVE: 'gold',
  SIGN: 'purple',
  LOGIN: 'cyan',
  LOGOUT: 'default',
  LOGIN_FAILED: 'volcano',
  EXPORT: 'magenta',
};

const ACTION_OPTIONS = [
  'CREATE',
  'UPDATE',
  'DELETE',
  'APPROVE',
  'REJECT',
  'SIGN',
  'LOGIN',
  'LOGOUT',
  'LOGIN_FAILED',
  'EXPORT',
  'IMPORT',
  'PERMISSION_CHANGE',
  'RESTORE',
  'READ',
].map((a) => ({ value: a, label: a }));

const ENTITY_TABLE_OPTIONS = [
  'substance',
  'substance_protein',
  'substance_xref',
  'project',
  'project_milestone',
  'project_team',
  'project_substance',
  'project_asset',
  'asset',
  'asset_market_id',
  'asset_substance',
  'material',
  'material_batch',
  'user',
  'role',
].map((t) => ({ value: t, label: t }));

export function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<AuditLogQuery>({});
  const [pendingQ, setPendingQ] = useState('');
  const [pendingUser, setPendingUser] = useState('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-audit-logs', page, pageSize, filters],
    queryFn: () => adminAuditApi.list({ ...filters, page, page_size: pageSize }),
  });

  const exportMutation = useMutation({
    mutationFn: () => adminAuditApi.exportCsv(filters),
    onSuccess: ({ blob, filename, rowCount }) => {
      // 触发浏览器下载
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      message.success(`已导出 ${rowCount} 行（${filename}）`);
    },
    onError: () => message.error('导出失败'),
  });

  const onDateChange = (range: [Dayjs | null, Dayjs | null] | null) => {
    setPage(1);
    setFilters((f) => ({
      ...f,
      date_from: range?.[0]?.toISOString(),
      date_to: range?.[1]?.toISOString(),
    }));
  };

  const items: AuditLogItem[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 170,
      render: (v: string) => <TimeDisplay value={v} />,
    },
    {
      title: '工号',
      dataIndex: 'username',
      key: 'username',
      width: 110,
    },
    {
      title: '姓名',
      dataIndex: 'full_name',
      key: 'full_name',
      width: 120,
      render: (v: string | null | undefined) => v || '—',
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 110,
      render: (v: string) => <Tag color={ACTION_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '对象表',
      dataIndex: 'entity_table',
      key: 'entity_table',
      width: 160,
      render: (v: string | null, row: AuditLogItem) => (
        <span>{v ?? '—'}{v === 'project_relationship' && row.change_summary && (
          <Text type="secondary" style={{ display: 'block' }}>{row.change_summary}</Text>
        )}</span>
      ),
    },
    {
      title: '编码',
      dataIndex: 'entity_code',
      key: 'entity_code',
      width: 160,
      render: (v: string | null) =>
        v ? <Text code>{v}</Text> : <Text type="secondary">—</Text>,
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
      render: (v: string | null) =>
        v ? <Text>{v}</Text> : <Text type="secondary" italic>（未填）</Text>,
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 130,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: 'Request',
      dataIndex: 'request_id',
      key: 'request_id',
      width: 130,
      render: (v: string | null) =>
        v ? (
          <Tooltip title={v}>
            <Text code style={{ fontSize: 11 }}>
              {v.slice(0, 12)}…
            </Text>
          </Tooltip>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '审计日志' }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <Title level={3} style={{ margin: 0 }}>
              <AuditOutlined style={{ marginRight: 8 }} />
              审计日志（全局）
            </Title>
            <Text type="secondary">
              共 {total} 条记录。点击行展开查看字段级变更。
            </Text>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={exportMutation.isPending}
              onClick={() => exportMutation.mutate()}
            >
              导出 CSV
            </Button>
          </Space>
        </div>
      </Card>

      <Card>
        <AdminTabs />
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            placeholder="搜索 编码 / 原因..."
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 240 }}
            value={pendingQ}
            onChange={(e) => setPendingQ(e.target.value)}
            onPressEnter={() => {
              setPage(1);
              setFilters((f) => ({ ...f, q: pendingQ || undefined }));
            }}
          />
          <Input
            placeholder="工号"
            allowClear
            style={{ width: 180 }}
            value={pendingUser}
            onChange={(e) => setPendingUser(e.target.value)}
            onPressEnter={() => {
              setPage(1);
              setFilters((f) => ({ ...f, username: pendingUser || undefined }));
            }}
          />
          <Select
            placeholder="动作"
            allowClear
            style={{ width: 160 }}
            value={filters.action}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, action: v }));
            }}
            options={ACTION_OPTIONS}
            showSearch
          />
          <Select
            placeholder="对象表"
            allowClear
            style={{ width: 200 }}
            value={filters.entity_table}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, entity_table: v }));
            }}
            options={ENTITY_TABLE_OPTIONS}
            showSearch
          />
          <RangePicker
            showTime
            value={
              filters.date_from || filters.date_to
                ? [
                    filters.date_from ? dayjs(filters.date_from) : null,
                    filters.date_to ? dayjs(filters.date_to) : null,
                  ]
                : undefined
            }
            onChange={onDateChange as never}
          />
          <Button
            onClick={() => {
              setPendingQ('');
              setPendingUser('');
              setFilters({});
              setPage(1);
            }}
          >
            重置
          </Button>
        </Space>
        <Table<AuditLogItem>
          columns={columns}
          dataSource={items}
          rowKey="log_id"
          loading={isLoading}
          expandable={{
            expandedRowRender: (row) => <ChangesView changes={row.changes} />,
            rowExpandable: () => true,
          }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: [10, 20, 50, 100, 200],
            onChange: (p, size) => {
              setPage(p);
              setPageSize(size);
            },
          }}
          scroll={{ x: 1420 }}
        />
      </Card>
    </div>
  );
}
