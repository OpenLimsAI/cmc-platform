import { useState } from 'react';
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
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
import { materialsApi } from '@/api/materials';
import type {
  MaterialBatch,
  MaterialBatchCreatePayload,
  MaterialBatchStatus,
  MaterialBatchUpdatePayload,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { MATERIAL_BATCH_STATUS_OPTIONS } from '../constants';

const { Text } = Typography;

interface FormValues {
  batch_number: string;
  quantity_value?: number | null;
  quantity_unit?: string;
  manufacture_date?: Dayjs | null;
  expiry_date?: Dayjs | null;
  receive_date?: Dayjs | null;
  source_batch_ref?: string;
  storage_location?: string;
  coa_url?: string;
  status?: MaterialBatchStatus;
  notes?: string;
  change_reason?: string;
}

interface Props {
  materialCode: string;
}

function statusTag(s: string) {
  const def = MATERIAL_BATCH_STATUS_OPTIONS.find((o) => o.value === s);
  return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
}

function toIso(d?: Dayjs | null): string | undefined {
  return d ? d.format('YYYY-MM-DD') : undefined;
}

export function BatchTable({ materialCode }: Props) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<MaterialBatch | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<MaterialBatch | null>(null);
  const [form] = Form.useForm<FormValues>();
  const [deleteForm] = Form.useForm<{ reason: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['material-batches', materialCode],
    queryFn: () => materialsApi.listBatches(materialCode),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['material-batches', materialCode] });
    queryClient.invalidateQueries({ queryKey: ['material-audit-logs', materialCode] });
  };

  const addMutation = useMutation({
    mutationFn: (payload: MaterialBatchCreatePayload) =>
      materialsApi.addBatch(materialCode, payload),
    onSuccess: () => {
      message.success('批次已添加');
      invalidate();
      setCreating(false);
      form.resetFields();
    },
    onError: (err: any) => {
      const apiCode = err?.response?.data?.code;
      if (apiCode === 44001) {
        message.error('同物料下批号重复');
      } else {
        message.error(err?.response?.data?.message ?? '添加失败');
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ batch_id, payload }: { batch_id: number; payload: MaterialBatchUpdatePayload }) =>
      materialsApi.updateBatch(materialCode, batch_id, payload),
    onSuccess: () => {
      message.success('已更新');
      invalidate();
      setEditing(null);
      form.resetFields();
    },
    onError: (err: any) => {
      const apiCode = err?.response?.data?.code;
      if (apiCode === 44001) {
        message.error('同物料下批号重复');
      } else {
        message.error(err?.response?.data?.message ?? '更新失败');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ batch_id, reason }: { batch_id: number; reason: string }) =>
      materialsApi.deleteBatch(materialCode, batch_id, reason),
    onSuccess: () => {
      message.success('已删除');
      invalidate();
      setDeleting(null);
      deleteForm.resetFields();
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? '删除失败');
    },
  });

  const onSubmit = (values: FormValues) => {
    const payload = {
      batch_number: values.batch_number,
      quantity_value:
        values.quantity_value !== undefined && values.quantity_value !== null
          ? String(values.quantity_value)
          : undefined,
      quantity_unit: values.quantity_unit || undefined,
      manufacture_date: toIso(values.manufacture_date),
      expiry_date: toIso(values.expiry_date),
      receive_date: toIso(values.receive_date),
      source_batch_ref: values.source_batch_ref || undefined,
      storage_location: values.storage_location || undefined,
      coa_url: values.coa_url || undefined,
      notes: values.notes || undefined,
    };
    if (editing) {
      updateMutation.mutate({
        batch_id: editing.batch_id,
        payload: {
          ...payload,
          status: values.status,
          change_reason: values.change_reason || undefined,
        },
      });
    } else {
      addMutation.mutate(payload);
    }
  };

  const openCreate = () => {
    form.resetFields();
    setCreating(true);
  };

  const openEdit = (b: MaterialBatch) => {
    setEditing(b);
    form.setFieldsValue({
      batch_number: b.batch_number,
      quantity_value: b.quantity_value ? Number(b.quantity_value) : undefined,
      quantity_unit: b.quantity_unit ?? undefined,
      manufacture_date: b.manufacture_date ? dayjs(b.manufacture_date) : undefined,
      expiry_date: b.expiry_date ? dayjs(b.expiry_date) : undefined,
      receive_date: b.receive_date ? dayjs(b.receive_date) : undefined,
      source_batch_ref: b.source_batch_ref ?? undefined,
      storage_location: b.storage_location ?? undefined,
      coa_url: b.coa_url ?? undefined,
      status: b.status,
      notes: b.notes ?? undefined,
    });
  };

  const isOpen = creating || editing !== null;

  const columns = [
    {
      title: '批号',
      dataIndex: 'batch_number',
      key: 'batch_number',
      width: 160,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '数量',
      key: 'quantity',
      width: 140,
      render: (_: unknown, b: MaterialBatch) =>
        b.quantity_value !== null && b.quantity_value !== undefined
          ? `${b.quantity_value} ${b.quantity_unit ?? ''}`.trim()
          : '—',
    },
    {
      title: '生产日期',
      dataIndex: 'manufacture_date',
      key: 'manufacture_date',
      width: 110,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '有效期',
      dataIndex: 'expiry_date',
      key: 'expiry_date',
      width: 110,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '到货日期',
      dataIndex: 'receive_date',
      key: 'receive_date',
      width: 110,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: statusTag,
    },
    {
      title: '存储位置',
      dataIndex: 'storage_location',
      key: 'storage_location',
      width: 140,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      render: (_: unknown, b: MaterialBatch) => (
        <PermissionGuard permission="material:update">
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(b)} />
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => setDeleting(b)}
            />
          </Space>
        </PermissionGuard>
      ),
    },
  ];

  return (
    <Card
      title="批次列表"
      extra={
        <PermissionGuard permission="material:update">
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            添加批次
          </Button>
        </PermissionGuard>
      }
    >
      <Table<MaterialBatch>
        columns={columns}
        dataSource={data ?? []}
        rowKey="batch_id"
        loading={isLoading}
        pagination={false}
        scroll={{ x: 1100 }}
      />

      <Modal
        title={editing ? `编辑批次 ${editing.batch_number}` : '添加批次'}
        open={isOpen}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText={editing ? '保存' : '添加'}
        confirmLoading={addMutation.isPending || updateMutation.isPending}
        width={680}
      >
        <Form<FormValues> form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item
            label="批号"
            name="batch_number"
            rules={[{ required: true, message: '请填写批号' }]}
          >
            <Input maxLength={64} placeholder="物理批号" />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="数量" name="quantity_value" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} min={0} step={0.0001} precision={4} />
            </Form.Item>
            <Form.Item label="单位" name="quantity_unit" style={{ flex: 1 }}>
              <Input maxLength={16} placeholder="mg / g / mL / vial" />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="生产日期" name="manufacture_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="有效期" name="expiry_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="到货日期" name="receive_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          {editing && (
            <Form.Item label="状态" name="status">
              <Select options={MATERIAL_BATCH_STATUS_OPTIONS} />
            </Form.Item>
          )}

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="存储位置" name="storage_location" style={{ flex: 1 }}>
              <Input maxLength={128} />
            </Form.Item>
            <Form.Item label="来源批号引用" name="source_batch_ref" style={{ flex: 1 }}>
              <Input maxLength={128} placeholder="供应商原批号 / 工艺单号" />
            </Form.Item>
          </Space>

          <Form.Item label="COA URL" name="coa_url">
            <Input placeholder="检验证书链接（可选）" />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>

          {editing && (
            <Form.Item label="变更原因" name="change_reason">
              <Input.TextArea rows={2} placeholder="写入审计日志（建议填写）" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title="删除批次"
        open={deleting !== null}
        onCancel={() => {
          setDeleting(null);
          deleteForm.resetFields();
        }}
        onOk={() => deleteForm.submit()}
        okText="确认删除"
        okButtonProps={{ danger: true }}
        confirmLoading={deleteMutation.isPending}
      >
        <p>
          确认删除批次 <Text code>{deleting?.batch_number}</Text>？此操作为软删除，记录会
          保留在审计日志中。
        </p>
        <Form<{ reason: string }>
          form={deleteForm}
          layout="vertical"
          onFinish={(v) => {
            if (deleting) {
              deleteMutation.mutate({ batch_id: deleting.batch_id, reason: v.reason });
            }
          }}
        >
          <Form.Item
            label="删除原因"
            name="reason"
            rules={[
              { required: true, message: '请填写删除原因' },
              { min: 5, message: '至少 5 个字符' },
            ]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
