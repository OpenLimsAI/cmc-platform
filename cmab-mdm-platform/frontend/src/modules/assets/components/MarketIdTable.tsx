import { useState } from 'react';
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs, { type Dayjs } from 'dayjs';
import { assetsApi } from '@/api/assets';
import type {
  AssetMarketId,
  AssetMarketIdCreatePayload,
  AssetMarketIdUpdatePayload,
  MarketIdStatus,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  MARKET_CODE_OPTIONS,
  MARKET_ID_STATUS_OPTIONS,
  MARKET_ID_TYPE_SUGGESTIONS,
} from '../constants';

const { Text } = Typography;

interface FormValues {
  market_code: string;
  id_type: string;
  id_value: string;
  issuing_authority?: string;
  application_date?: Dayjs;
  approval_date?: Dayjs;
  expiry_date?: Dayjs;
  status?: MarketIdStatus;
  notes?: string;
  change_reason?: string;
}

interface Props {
  assetCode: string;
}

export function MarketIdTable({ assetCode }: Props) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AssetMarketId | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<AssetMarketId | null>(null);
  const [form] = Form.useForm<FormValues>();
  const [deleteForm] = Form.useForm<{ reason: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['asset-market-ids', assetCode],
    queryFn: () => assetsApi.listMarketIds(assetCode),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['asset-market-ids', assetCode] });
    queryClient.invalidateQueries({ queryKey: ['asset-audit-logs', assetCode] });
  };

  const addMutation = useMutation({
    mutationFn: (payload: AssetMarketIdCreatePayload) =>
      assetsApi.addMarketId(assetCode, payload),
    onSuccess: () => {
      message.success('多市场注册号已添加');
      invalidate();
      setCreating(false);
      form.resetFields();
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) message.error('已存在相同的 (市场, ID 类型, ID 值) 组合');
      else message.error(err?.response?.data?.message ?? '添加失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      pk,
      payload,
    }: {
      pk: number;
      payload: AssetMarketIdUpdatePayload;
    }) => assetsApi.updateMarketId(assetCode, pk, payload),
    onSuccess: () => {
      message.success('已更新');
      invalidate();
      setEditing(null);
      form.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ pk, reason }: { pk: number; reason: string }) =>
      assetsApi.deleteMarketId(assetCode, pk, reason),
    onSuccess: () => {
      message.success('已删除');
      invalidate();
      setDeleting(null);
      deleteForm.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '删除失败'),
  });

  const onSubmit = async () => {
    const v = await form.validateFields();
    const base = {
      market_code: v.market_code,
      id_type: v.id_type,
      id_value: v.id_value,
      issuing_authority: v.issuing_authority,
      application_date: v.application_date?.format('YYYY-MM-DD'),
      approval_date: v.approval_date?.format('YYYY-MM-DD'),
      expiry_date: v.expiry_date?.format('YYYY-MM-DD'),
      status: v.status,
      notes: v.notes,
    };
    if (editing) {
      updateMutation.mutate({
        pk: editing.market_id_pk,
        payload: { ...base, change_reason: v.change_reason },
      });
    } else {
      addMutation.mutate(base as AssetMarketIdCreatePayload);
    }
  };

  const onSubmitDelete = async () => {
    const v = await deleteForm.validateFields();
    if (!deleting) return;
    deleteMutation.mutate({ pk: deleting.market_id_pk, reason: v.reason });
  };

  const openCreate = () => {
    setCreating(true);
    form.resetFields();
    form.setFieldsValue({ market_code: 'CN', id_type: 'NMPA_APPROVAL' });
  };

  const openEdit = (m: AssetMarketId) => {
    setEditing(m);
    form.setFieldsValue({
      market_code: m.market_code,
      id_type: m.id_type,
      id_value: m.id_value,
      issuing_authority: m.issuing_authority ?? undefined,
      application_date: m.application_date ? dayjs(m.application_date) : undefined,
      approval_date: m.approval_date ? dayjs(m.approval_date) : undefined,
      expiry_date: m.expiry_date ? dayjs(m.expiry_date) : undefined,
      status: m.status ?? undefined,
      notes: m.notes ?? undefined,
    });
  };

  const columns = [
    {
      title: '市场',
      dataIndex: 'market_code',
      width: 100,
      render: (v: string) =>
        MARKET_CODE_OPTIONS.find((o) => o.value === v)?.label ?? v,
    },
    { title: 'ID 类型', dataIndex: 'id_type', width: 140 },
    { title: 'ID 值', dataIndex: 'id_value', ellipsis: true },
    {
      title: '发证机构',
      dataIndex: 'issuing_authority',
      width: 120,
      render: (v?: string | null) => v ?? '—',
    },
    { title: '申请日期', dataIndex: 'application_date', width: 110, render: (v?: string) => v ?? '—' },
    { title: '批准日期', dataIndex: 'approval_date', width: 110, render: (v?: string) => v ?? '—' },
    { title: '失效日期', dataIndex: 'expiry_date', width: 110, render: (v?: string) => v ?? '—' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s?: string | null) => {
        if (!s) return '—';
        const def = MARKET_ID_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: unknown, row: AssetMarketId) => (
        <Space>
          <PermissionGuard permission="asset:update">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>
              编辑
            </Button>
          </PermissionGuard>
          <PermissionGuard permission="asset:update">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                setDeleting(row);
                deleteForm.resetFields();
              }}
            >
              删除
            </Button>
          </PermissionGuard>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="多市场注册号"
      extra={
        <PermissionGuard permission="asset:update">
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            添加注册号
          </Button>
        </PermissionGuard>
      }
    >
      <Table<AssetMarketId>
        size="middle"
        rowKey="market_id_pk"
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">暂无注册号</Text> }}
      />

      <Modal
        open={creating || editing !== null}
        title={editing ? `编辑注册号 #${editing.market_id_pk}` : '添加多市场注册号'}
        onCancel={() => {
          setEditing(null);
          setCreating(false);
          form.resetFields();
        }}
        onOk={onSubmit}
        confirmLoading={addMutation.isPending || updateMutation.isPending}
        destroyOnClose
        width={720}
      >
        <Form form={form} layout="vertical">
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="市场" name="market_code" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={MARKET_CODE_OPTIONS} />
            </Form.Item>
            <Form.Item label="ID 类型" name="id_type" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select
                showSearch
                allowClear
                placeholder="选择或输入"
                options={MARKET_ID_TYPE_SUGGESTIONS.map((s) => ({ value: s, label: s }))}
                filterOption={(input, option) =>
                  (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
                }
              />
            </Form.Item>
          </Space>
          <Form.Item label="ID 值" name="id_value" rules={[{ required: true }]}>
            <Input maxLength={128} placeholder="例：国药准字 S20260001 / NDC-XXXXX" />
          </Form.Item>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="发证机构" name="issuing_authority" style={{ flex: 1 }}>
              <Input maxLength={128} />
            </Form.Item>
            <Form.Item label="状态" name="status" style={{ flex: 1 }}>
              <Select allowClear options={MARKET_ID_STATUS_OPTIONS} />
            </Form.Item>
          </Space>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="申请日期" name="application_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="批准日期" name="approval_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="失效日期" name="expiry_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>
          {editing && (
            <Form.Item label="变更原因" name="change_reason">
              <Input.TextArea rows={2} placeholder="将写入审计日志" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        open={deleting !== null}
        title={
          deleting
            ? `删除注册号：${deleting.market_code}/${deleting.id_type}/${deleting.id_value}`
            : ''
        }
        okText="确认删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        onCancel={() => {
          setDeleting(null);
          deleteForm.resetFields();
        }}
        onOk={onSubmitDelete}
        confirmLoading={deleteMutation.isPending}
        destroyOnClose
      >
        <Form form={deleteForm} layout="vertical">
          <Form.Item
            label="变更原因（最少 5 字）"
            name="reason"
            rules={[
              { required: true, message: '必须填写变更原因' },
              { min: 5, message: '原因至少 5 字' },
            ]}
          >
            <Input.TextArea rows={3} placeholder="说明删除此注册号的业务原因" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
