import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  DatePicker,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import { useQuery } from '@tanstack/react-query';
import { adminSignaturesApi } from '@/api/admin';
import type { SignatureItem, SignatureQuery } from '@/api/types';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { AdminTabs } from '../components/AdminTabs';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

const MEANING_COLOR: Record<string, string> = {
  approve: 'gold',
  review: 'blue',
  release: 'green',
  witness: 'purple',
  reject: 'red',
};

const MEANING_LABEL: Record<string, string> = {
  approve: '审批',
  review: '复核',
  release: '放行',
  witness: '见证',
  reject: '驳回',
};

const MEANING_OPTIONS = Object.entries(MEANING_LABEL).map(([v, l]) => ({
  value: v,
  label: `${l} (${v})`,
}));

const ENTITY_TABLE_OPTIONS = [
  'substance',
  'project',
  'asset',
].map((t) => ({ value: t, label: t }));

export function SignatureListPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<SignatureQuery>({});
  const [pendingUser, setPendingUser] = useState('');
  const [detail, setDetail] = useState<SignatureItem | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-signatures', page, pageSize, filters],
    queryFn: () =>
      adminSignaturesApi.list({ ...filters, page, page_size: pageSize }),
  });

  const items: SignatureItem[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const onDateChange = (range: [Dayjs | null, Dayjs | null] | null) => {
    setPage(1);
    setFilters((f) => ({
      ...f,
      date_from: range?.[0]?.toISOString(),
      date_to: range?.[1]?.toISOString(),
    }));
  };

  const columns = [
    {
      title: '签名 ID',
      dataIndex: 'signature_id',
      key: 'signature_id',
      width: 100,
      render: (v: number) => <Text code>{v}</Text>,
    },
    {
      title: '签名时间',
      dataIndex: 'signed_at',
      key: 'signed_at',
      width: 170,
      render: (v: string) => <TimeDisplay value={v} />,
    },
    {
      title: '签名人',
      key: 'signer',
      width: 200,
      render: (_: unknown, r: SignatureItem) => (
        <span>
          <Text strong>{r.full_name}</Text>
          <Text type="secondary" style={{ marginLeft: 6 }}>
            ({r.username})
          </Text>
        </span>
      ),
    },
    {
      title: '含义',
      dataIndex: 'signature_meaning',
      key: 'signature_meaning',
      width: 110,
      render: (v: string) => (
        <Tag color={MEANING_COLOR[v] ?? 'default'}>{MEANING_LABEL[v] ?? v}</Tag>
      ),
    },
    {
      title: '对象',
      key: 'entity',
      width: 220,
      render: (_: unknown, r: SignatureItem) => (
        <span>
          <Tag>{r.entity_table}</Tag>
          {r.entity_code && <Text code>{r.entity_code}</Text>}
        </span>
      ),
    },
    {
      title: '理由',
      dataIndex: 'signature_reason',
      key: 'signature_reason',
      ellipsis: true,
    },
    {
      title: '内容哈希',
      dataIndex: 'signed_content_hash',
      key: 'signed_content_hash',
      width: 130,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text code style={{ fontSize: 11 }}>
            {v.slice(0, 10)}…
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, r: SignatureItem) => (
        <Button type="link" onClick={() => setDetail(r)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: '系统管理' }, { title: '电子签名' }]}
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
              <SafetyCertificateOutlined style={{ marginRight: 8 }} />
              电子签名（21 CFR Part 11 §11.50）
            </Title>
            <Text type="secondary">
              共 {total} 条签名记录。所有 GxP 关键状态变更均留有签名链。
            </Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
            刷新
          </Button>
        </div>
      </Card>

      <Card>
        <AdminTabs />
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            placeholder="签名人 username"
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
            placeholder="对象表"
            allowClear
            style={{ width: 160 }}
            value={filters.entity_table}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, entity_table: v }));
            }}
            options={ENTITY_TABLE_OPTIONS}
          />
          <Select
            placeholder="签名含义"
            allowClear
            style={{ width: 180 }}
            value={filters.signature_meaning}
            onChange={(v) => {
              setPage(1);
              setFilters((f) => ({ ...f, signature_meaning: v }));
            }}
            options={MEANING_OPTIONS}
          />
          <Input
            placeholder="实体编码"
            allowClear
            style={{ width: 180 }}
            value={filters.entity_code ?? ''}
            onChange={(e) => {
              const v = e.target.value;
              setPage(1);
              setFilters((f) => ({ ...f, entity_code: v || undefined }));
            }}
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
              setPendingUser('');
              setFilters({});
              setPage(1);
            }}
          >
            重置
          </Button>
        </Space>
        <Table<SignatureItem>
          columns={columns}
          dataSource={items}
          rowKey="signature_id"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: [10, 20, 50, 100],
            onChange: (p, size) => {
              setPage(p);
              setPageSize(size);
            },
          }}
          scroll={{ x: 1500 }}
        />
      </Card>

      <Modal
        title={`签名详情 #${detail?.signature_id ?? ''}`}
        open={detail !== null}
        onCancel={() => setDetail(null)}
        footer={null}
        width={640}
      >
        {detail && (
          <div>
            <Paragraph>
              <Text strong>签名人：</Text> {detail.full_name} ({detail.username})
            </Paragraph>
            <Paragraph>
              <Text strong>时间：</Text> <TimeDisplay value={detail.signed_at} />
            </Paragraph>
            <Paragraph>
              <Text strong>含义：</Text>{' '}
              <Tag color={MEANING_COLOR[detail.signature_meaning] ?? 'default'}>
                {MEANING_LABEL[detail.signature_meaning] ?? detail.signature_meaning}
              </Tag>
            </Paragraph>
            <Paragraph>
              <Text strong>对象：</Text> <Tag>{detail.entity_table}</Tag>
              {detail.entity_code && <Text code>{detail.entity_code}</Text>}{' '}
              <Text type="secondary">(id={detail.entity_id})</Text>
            </Paragraph>
            <Paragraph>
              <Text strong>理由：</Text>
              <br />
              {detail.signature_reason}
            </Paragraph>
            <Paragraph>
              <Text strong>内容哈希（SHA-256）：</Text>
              <br />
              <Text code style={{ fontSize: 11 }}>{detail.signed_content_hash}</Text>
            </Paragraph>
            <Paragraph>
              <Text strong>签名哈希（SHA-256）：</Text>
              <br />
              <Text code style={{ fontSize: 11 }}>{detail.signature_hash}</Text>
            </Paragraph>
          </div>
        )}
      </Modal>
    </div>
  );
}
