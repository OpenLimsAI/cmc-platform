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
import { projectsApi } from '@/api/projects';
import type {
  MilestoneStatus,
  MilestoneType,
  ProjectMilestone,
  ProjectMilestoneCreatePayload,
  ProjectMilestoneUpdatePayload,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  MILESTONE_STATUS_OPTIONS,
  MILESTONE_TYPE_OPTIONS,
} from '../constants';

const { Text } = Typography;

interface FormValues {
  milestone_name: string;
  milestone_type: MilestoneType;
  planned_date?: Dayjs;
  actual_date?: Dayjs;
  status: MilestoneStatus;
  description?: string;
  change_reason?: string;
}

interface Props {
  projectCode: string;
}

export function MilestoneTable({ projectCode }: Props) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<ProjectMilestone | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ProjectMilestone | null>(null);
  const [form] = Form.useForm<FormValues>();
  const [deleteForm] = Form.useForm<{ reason: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['project-milestones', projectCode],
    queryFn: () => projectsApi.listMilestones(projectCode),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['project-milestones', projectCode] });
    queryClient.invalidateQueries({ queryKey: ['project-audit-logs', projectCode] });
  };

  const addMutation = useMutation({
    mutationFn: (payload: ProjectMilestoneCreatePayload) =>
      projectsApi.addMilestone(projectCode, payload),
    onSuccess: () => {
      message.success('里程碑已添加');
      invalidate();
      setCreating(false);
      form.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '添加失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ mid, payload }: { mid: number; payload: ProjectMilestoneUpdatePayload }) =>
      projectsApi.updateMilestone(projectCode, mid, payload),
    onSuccess: () => {
      message.success('里程碑已更新');
      invalidate();
      setEditing(null);
      form.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ mid, reason }: { mid: number; reason: string }) =>
      projectsApi.deleteMilestone(projectCode, mid, reason),
    onSuccess: () => {
      message.success('里程碑已删除');
      invalidate();
      setDeleting(null);
      deleteForm.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '删除失败'),
  });

  const submitDelete = async () => {
    const v = await deleteForm.validateFields();
    if (!deleting) return;
    deleteMutation.mutate({ mid: deleting.milestone_id, reason: v.reason });
  };

  const onSubmit = async () => {
    const values = await form.validateFields();
    const base = {
      milestone_name: values.milestone_name,
      milestone_type: values.milestone_type,
      status: values.status,
      description: values.description,
      planned_date: values.planned_date?.format('YYYY-MM-DD'),
      actual_date: values.actual_date?.format('YYYY-MM-DD'),
    };
    if (editing) {
      updateMutation.mutate({
        mid: editing.milestone_id,
        payload: { ...base, change_reason: values.change_reason },
      });
    } else {
      addMutation.mutate(base as ProjectMilestoneCreatePayload);
    }
  };

  const openEdit = (m: ProjectMilestone) => {
    setEditing(m);
    form.setFieldsValue({
      milestone_name: m.milestone_name,
      milestone_type: m.milestone_type ?? undefined,
      planned_date: dayjs(m.planned_date),
      actual_date: m.actual_date ? dayjs(m.actual_date) : undefined,
      status: m.status,
      description: m.description ?? undefined,
    });
  };

  const openCreate = () => {
    setCreating(true);
    form.resetFields();
    form.setFieldsValue({ status: 'planned', milestone_type: 'gate' });
  };

  const columns = [
    { title: '名称', dataIndex: 'milestone_name', ellipsis: true },
    {
      title: '类型',
      dataIndex: 'milestone_type',
      width: 110,
      render: (t: string) => MILESTONE_TYPE_OPTIONS.find((o) => o.value === t)?.label ?? t,
    },
    { title: '计划日期', dataIndex: 'planned_date', width: 110, render: (v?: string) => v ?? '—' },
    { title: '实际日期', dataIndex: 'actual_date', width: 110, render: (v?: string) => v ?? '—' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => {
        const def = MILESTONE_STATUS_OPTIONS.find((o) => o.value === s);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? s}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: unknown, row: ProjectMilestone) => (
        <Space>
          <PermissionGuard permission="project:update">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>
              编辑
            </Button>
          </PermissionGuard>
          <PermissionGuard permission="project:update">
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
      title="里程碑"
      extra={
        <PermissionGuard permission="project:update">
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            添加里程碑
          </Button>
        </PermissionGuard>
      }
    >
      <Table<ProjectMilestone>
        size="middle"
        rowKey="milestone_id"
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">暂无里程碑</Text> }}
        expandable={{
          expandedRowRender: (row) =>
            row.description ? <Text>{row.description}</Text> : <Text type="secondary">无描述</Text>,
          rowExpandable: () => true,
        }}
      />

      <Modal
        open={creating || editing !== null}
        title={editing ? `编辑里程碑 #${editing.milestone_id}` : '添加里程碑'}
        onCancel={() => {
          setEditing(null);
          setCreating(false);
          form.resetFields();
        }}
        onOk={onSubmit}
        confirmLoading={addMutation.isPending || updateMutation.isPending}
        destroyOnClose
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="里程碑名称"
            name="milestone_name"
            rules={[{ required: true, message: '必填' }]}
          >
            <Input maxLength={255} placeholder="例：IND 申报、Tox study completion" />
          </Form.Item>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="类型" name="milestone_type" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={MILESTONE_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item label="状态" name="status" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={MILESTONE_STATUS_OPTIONS} />
            </Form.Item>
          </Space>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="计划日期" name="planned_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="实际日期" name="actual_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          {editing && (
            <Form.Item
              label="变更原因"
              name="change_reason"
              tooltip="将写入审计日志。建议填写。"
            >
              <Input.TextArea rows={2} />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        open={deleting !== null}
        title={deleting ? `删除里程碑：${deleting.milestone_name}` : ''}
        okText="确认删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        onCancel={() => {
          setDeleting(null);
          deleteForm.resetFields();
        }}
        onOk={submitDelete}
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
            <Input.TextArea rows={3} placeholder="说明删除此里程碑的业务原因" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
