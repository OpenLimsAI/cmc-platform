import { useState } from 'react';
import { Button, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, message } from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { substancesApi } from '@/api/substances';
import type {
  SubstanceXref,
  SubstanceXrefCreateInput,
  XrefType,
} from '@/api/types';
import { useAuthStore } from '@/stores/authStore';
import { XREF_TYPE_OPTIONS } from '../constants';

interface Props {
  substanceCode: string;
  xrefs: SubstanceXref[];
}

interface EditState {
  mode: 'create' | 'edit';
  xref?: SubstanceXref;
}

export function XrefEditor({ substanceCode, xrefs }: Props) {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const queryClient = useQueryClient();
  const canEdit = hasPermission('substance:update');
  const [editing, setEditing] = useState<EditState | null>(null);
  const [form] = Form.useForm<SubstanceXrefCreateInput>();

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['substance', substanceCode] });

  const createMutation = useMutation({
    mutationFn: (payload: SubstanceXrefCreateInput) =>
      substancesApi.addXref(substanceCode, payload),
    onSuccess: () => {
      message.success('标识符已添加');
      refresh();
      setEditing(null);
      form.resetFields();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ xrefId, payload }: { xrefId: number; payload: SubstanceXrefCreateInput }) =>
      substancesApi.updateXref(substanceCode, xrefId, payload),
    onSuccess: () => {
      message.success('标识符已更新');
      refresh();
      setEditing(null);
      form.resetFields();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (xrefId: number) => substancesApi.deleteXref(substanceCode, xrefId),
    onSuccess: () => {
      message.success('已删除');
      refresh();
    },
  });

  const handleAdd = () => {
    setEditing({ mode: 'create' });
    form.resetFields();
    form.setFieldsValue({ is_primary: false });
  };

  const handleEdit = (xref: SubstanceXref) => {
    setEditing({ mode: 'edit', xref });
    form.setFieldsValue({
      xref_type: xref.xref_type as XrefType,
      xref_value: xref.xref_value,
      xref_source: xref.xref_source ?? undefined,
      is_primary: xref.is_primary,
      notes: xref.notes ?? undefined,
    });
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (editing?.mode === 'create') {
      createMutation.mutate(values);
    } else if (editing?.mode === 'edit' && editing.xref?.xref_id) {
      updateMutation.mutate({ xrefId: editing.xref.xref_id, payload: values });
    }
  };

  const columns = [
    {
      title: '类型',
      dataIndex: 'xref_type',
      width: 110,
      render: (t: string, row: SubstanceXref) => (
        <Tag color={row.is_primary ? 'blue' : 'default'}>
          {t}
          {row.is_primary ? ' ★' : ''}
        </Tag>
      ),
    },
    { title: '值', dataIndex: 'xref_value' },
    { title: '来源', dataIndex: 'xref_source', width: 140, render: (v?: string) => v || '—' },
    { title: '备注', dataIndex: 'notes', render: (v?: string) => v || '—' },
    {
      title: '操作',
      width: 130,
      render: (_: unknown, row: SubstanceXref) =>
        canEdit ? (
          <Space size="small">
            <Button size="small" type="link" icon={<EditOutlined />} onClick={() => handleEdit(row)}>
              编辑
            </Button>
            <Popconfirm
              title="确定删除该标识符？"
              onConfirm={() => row.xref_id && deleteMutation.mutate(row.xref_id)}
            >
              <Button size="small" type="link" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
        <span>共 {xrefs.length} 条</span>
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加标识符
          </Button>
        )}
      </div>

      <Table<SubstanceXref>
        size="small"
        rowKey={(r) => r.xref_id ?? `${r.xref_type}:${r.xref_value}`}
        columns={columns}
        dataSource={xrefs}
        pagination={false}
        locale={{ emptyText: '暂无标识符' }}
      />

      <Modal
        open={editing !== null}
        title={editing?.mode === 'create' ? '添加标识符' : '编辑标识符'}
        onCancel={() => {
          setEditing(null);
          form.resetFields();
        }}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        okText="保存"
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="xref_type" label="类型" rules={[{ required: true }]}>
            <Select options={XREF_TYPE_OPTIONS} placeholder="选择标识符类型" />
          </Form.Item>
          <Form.Item name="xref_value" label="值" rules={[{ required: true, max: 255 }]}>
            <Input placeholder="如：trastuzumab biosimilar / 180288-69-1" />
          </Form.Item>
          <Form.Item name="xref_source" label="来源" rules={[{ max: 64 }]}>
            <Input placeholder="如 WHO / CAS / internal" />
          </Form.Item>
          <Form.Item name="is_primary" label="是否为该类型的主标识" valuePropName="checked">
            <Switch checkedChildren="主" unCheckedChildren="次" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
