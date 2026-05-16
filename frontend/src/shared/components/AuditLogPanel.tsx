import { useState } from 'react';
import { Card, Empty, Result, Switch, Table, Tag, Tooltip, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { AuditLogItem, ApiListResponse, ChangeHistoryItem, Pagination } from '@/api/types';

const { Text } = Typography;

const ACTION_COLOR: Record<string, string> = {
  CREATE: 'green',
  UPDATE: 'blue',
  DELETE: 'red',
  APPROVE: 'gold',
  SIGN: 'purple',
};

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '∅';
  if (typeof v === 'string') return v.length > 60 ? v.slice(0, 60) + '…' : v;
  if (typeof v === 'object') return JSON.stringify(v).slice(0, 80);
  return String(v);
}

export function ChangesView({ changes }: { changes: ChangeHistoryItem[] }) {
  if (changes.length === 0) {
    // v3 起 CREATE/DELETE 也展开字段；这里通常只在很老的历史日志（v2 时期）出现
    return <Text type="secondary">（该记录无字段级展开 — 早期 CREATE/DELETE 历史日志或纯状态翻转）</Text>;
  }
  return (
    <Table
      size="small"
      pagination={false}
      rowKey="field_name"
      dataSource={changes}
      columns={[
        { title: '字段', dataIndex: 'field_name', width: 180, render: (v: string) => <code>{v}</code> },
        {
          title: '原值',
          dataIndex: 'old_value',
          render: (v: unknown) => <Text type="secondary">{formatValue(v)}</Text>,
        },
        {
          title: '新值',
          dataIndex: 'new_value',
          render: (v: unknown) => <Text>{formatValue(v)}</Text>,
        },
      ]}
    />
  );
}

export interface AuditLogLoadResult {
  items: AuditLogItem[];
  pagination: Pagination;
}

interface Props {
  queryKey: readonly unknown[];
  loadFn: (page: number, pageSize: number, includeChildren: boolean) => Promise<AuditLogLoadResult>;
  tableLabels?: Record<string, string>;
}

/**
 * 通用审计日志面板。SRS / PRS / 未来 ARS / MM 共用，差异通过 props 注入：
 *   - queryKey：react-query 缓存键（包含 code 等）
 *   - loadFn：调具体域的 auditLogs API
 *   - tableLabels：把后端 entity_table（如 'substance_xref'）映射成中文标签
 */
export function AuditLogPanel({ queryKey, loadFn, tableLabels = {} }: Props) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [includeChildren, setIncludeChildren] = useState(true);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: [...queryKey, page, pageSize, includeChildren],
    queryFn: () => loadFn(page, pageSize, includeChildren),
  });

  if (isError) {
    const err = error as { response?: { status?: number } };
    if (err.response?.status === 403) {
      return (
        <Result
          status="403"
          title="无权查看审计日志"
          subTitle="需要 audit:read 权限。请联系系统管理员（QA / Steward 角色可查看）。"
        />
      );
    }
    return <Result status="error" title="加载失败" />;
  }

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 180,
      render: (v: string) => <Text>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</Text>,
    },
    {
      title: '操作',
      dataIndex: 'action',
      width: 100,
      render: (v: string) => <Tag color={ACTION_COLOR[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '对象',
      dataIndex: 'entity_table',
      width: 150,
      render: (t: string, row: AuditLogItem) => (
        <span>
          {tableLabels[t] || t}
          {row.entity_code && (
            <Text type="secondary" style={{ marginLeft: 4 }}>
              {row.entity_code}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: '操作人',
      dataIndex: 'username',
      width: 120,
    },
    {
      title: '变更原因',
      dataIndex: 'reason',
      render: (v?: string) =>
        v ? (
          <Text>{v}</Text>
        ) : (
          <Text type="secondary" italic>
            （未填）
          </Text>
        ),
    },
    {
      title: 'Request ID',
      dataIndex: 'request_id',
      width: 200,
      render: (v?: string) =>
        v ? (
          <Tooltip title={v}>
            <Text code style={{ fontSize: 11 }}>
              {v.slice(0, 14)}…
            </Text>
          </Tooltip>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <Card>
      <div
        style={{
          marginBottom: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Text type="secondary">
          共 {data?.pagination.total ?? 0} 条记录。点击行展开查看字段级变更。
        </Text>
        <Switch
          checked={includeChildren}
          onChange={(v) => {
            setIncludeChildren(v);
            setPage(1);
          }}
          checkedChildren="含子对象"
          unCheckedChildren="仅主表"
        />
      </div>

      <Table<AuditLogItem>
        size="middle"
        rowKey="log_id"
        loading={isLoading}
        dataSource={data?.items ?? []}
        columns={columns}
        expandable={{
          expandedRowRender: (row) => <ChangesView changes={row.changes} />,
          rowExpandable: () => true,
        }}
        locale={{ emptyText: <Empty description="暂无审计记录" /> }}
        pagination={{
          current: page,
          pageSize,
          total: data?.pagination.total ?? 0,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50, 100],
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, size) => {
            setPage(p);
            setPageSize(size);
          },
        }}
      />
    </Card>
  );
}

// 兼容旧 import：让其他文件平滑过渡（M2.1 已在 SubstanceDetailPage 切到 AuditLogPanel）
export type { AuditLogItem, ApiListResponse };
