import { useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, UserAddOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/api/projects';
import type {
  ProjectTeamMember,
  ProjectTeamMemberCreatePayload,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { TEAM_ROLE_SUGGESTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  projectCode: string;
}

interface AddFormValues {
  user_id: number;
  role: string;
  function_area?: string;
  allocation_pct?: number;
  notes?: string;
}

export function TeamTable({ projectCode }: Props) {
  const queryClient = useQueryClient();
  const [includeLeft, setIncludeLeft] = useState(false);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<ProjectTeamMember | null>(null);
  const [addForm] = Form.useForm<AddFormValues>();
  const [removeForm] = Form.useForm<{ reason?: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['project-team', projectCode, includeLeft],
    queryFn: () => projectsApi.listTeam(projectCode, includeLeft),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['project-team', projectCode] });
    queryClient.invalidateQueries({ queryKey: ['project-audit-logs', projectCode] });
  };

  const addMutation = useMutation({
    mutationFn: (payload: ProjectTeamMemberCreatePayload) =>
      projectsApi.addTeamMember(projectCode, payload),
    onSuccess: () => {
      message.success('成员已添加');
      invalidate();
      setAdding(false);
      addForm.resetFields();
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) {
        message.error('该用户已是项目此角色的成员');
      } else if (status === 400) {
        message.error('用户不存在或已停用');
      } else {
        message.error(err?.response?.data?.message ?? '添加失败');
      }
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ team_id, reason }: { team_id: number; reason?: string }) =>
      projectsApi.removeTeamMember(projectCode, team_id, reason),
    onSuccess: () => {
      message.success('成员已移除');
      invalidate();
      setRemoving(null);
      removeForm.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '移除失败'),
  });

  const submitAdd = async () => {
    const v = await addForm.validateFields();
    addMutation.mutate(v);
  };

  const submitRemove = async () => {
    const v = await removeForm.validateFields();
    if (!removing) return;
    removeMutation.mutate({ team_id: removing.team_id, reason: v.reason });
  };

  const columns = [
    { title: '成员 ID', dataIndex: 'user_id', width: 100 },
    {
      title: '角色',
      dataIndex: 'role',
      width: 130,
      render: (r: string) => <Tag>{r}</Tag>,
    },
    {
      title: '职能',
      dataIndex: 'function_area',
      width: 110,
      render: (v?: string | null) => v ?? '—',
    },
    {
      title: '投入',
      dataIndex: 'allocation_pct',
      width: 80,
      render: (v?: number | null) => (v != null ? `${v}%` : '—'),
    },
    {
      title: '加入时间',
      dataIndex: 'joined_at',
      width: 130,
      render: (v: string) => v,  // §9.4 DATE 类型，直接显示
    },
    {
      title: '离开时间',
      dataIndex: 'left_at',
      width: 130,
      render: (v?: string | null) => (v ? <Text type="danger">{v}</Text> : '—'),
    },
    { title: '备注', dataIndex: 'notes', ellipsis: true, render: (v?: string) => v ?? '—' },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: unknown, row: ProjectTeamMember) =>
        row.left_at ? (
          <Text type="secondary">已离开</Text>
        ) : (
          <PermissionGuard permission="project:update">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                setRemoving(row);
                removeForm.resetFields();
              }}
            >
              移除
            </Button>
          </PermissionGuard>
        ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <span>团队成员</span>
          <Switch
            checked={includeLeft}
            onChange={setIncludeLeft}
            checkedChildren="含已离开"
            unCheckedChildren="仅在岗"
            size="small"
          />
        </Space>
      }
      extra={
        <PermissionGuard permission="project:update">
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            onClick={() => {
              setAdding(true);
              addForm.resetFields();
              addForm.setFieldsValue({ role: 'Member' });
            }}
          >
            添加成员
          </Button>
        </PermissionGuard>
      }
    >
      <Table<ProjectTeamMember>
        size="middle"
        rowKey="team_id"
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">暂无成员</Text> }}
      />

      <Modal
        open={adding}
        title="添加团队成员"
        okText="添加"
        onCancel={() => {
          setAdding(false);
          addForm.resetFields();
        }}
        onOk={submitAdd}
        confirmLoading={addMutation.isPending}
        destroyOnClose
      >
        <Form form={addForm} layout="vertical">
          <Form.Item
            label="成员 user_id"
            name="user_id"
            rules={[{ required: true, message: '必填' }]}
            tooltip="暂用 user_id 数值；后续接入用户搜索下拉"
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="例：2" />
          </Form.Item>
          <Form.Item
            label="项目内角色"
            name="role"
            rules={[{ required: true }]}
            tooltip="§9.4：任意字符串。提供建议值，可自由输入"
          >
            <Select
              showSearch
              allowClear
              placeholder="选择或输入"
              options={TEAM_ROLE_SUGGESTIONS.map((r) => ({ value: r, label: r }))}
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item label="职能领域 (function_area)" name="function_area">
            <Input maxLength={64} placeholder="例：CMC / QA / Regulatory" />
          </Form.Item>
          <Form.Item label="投入百分比" name="allocation_pct">
            <InputNumber min={0} max={100} style={{ width: '100%' }} placeholder="0-100" />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={removing !== null}
        title={removing ? `移除成员 user_id=${removing.user_id}（${removing.role}）` : ''}
        okText="确认移除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        onCancel={() => {
          setRemoving(null);
          removeForm.resetFields();
        }}
        onOk={submitRemove}
        confirmLoading={removeMutation.isPending}
        destroyOnClose
      >
        <Form form={removeForm} layout="vertical">
          <Form.Item label="移除原因（写入审计；可选）" name="reason">
            <Input.TextArea rows={3} placeholder="说明移除原因" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
