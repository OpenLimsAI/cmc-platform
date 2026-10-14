import { useState } from 'react';
import {
  AutoComplete,
  Button,
  Card,
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
import { DeleteOutlined, ApartmentOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { projectsApi } from '@/api/projects';
import { searchApi } from '@/api/search';
import type {
  ProjectRelationshipCreatePayload,
  ProjectRelationshipItem,
  ProjectRelationshipType,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PROJECT_RELATIONSHIP_TYPE_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  projectCode: string;
}

interface AddForm {
  to_project_code: string;
  relationship_type: ProjectRelationshipType;
  change_reason: string;
  notes?: string;
}

function relationLabel(item: ProjectRelationshipItem): string {
  const def = PROJECT_RELATIONSHIP_TYPE_OPTIONS.find((o) => o.value === item.relationship_type);
  if (!def) return item.relationship_type;
  return item.direction === 'outgoing' ? def.outLabel : def.inLabel;
}

export function ProjectRelationshipTab({ projectCode }: Props) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [addForm] = Form.useForm<AddForm>();

  const { data, isLoading } = useQuery({
    queryKey: ['project-relationships', projectCode],
    queryFn: () => projectsApi.listRelationships(projectCode),
  });

  const { data: searchHits } = useQuery({
    queryKey: ['search-project-for-relationship', searchQ],
    queryFn: () => searchApi.search(searchQ, 'project', 20),
    enabled: adding && searchQ.trim().length > 0,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['project-relationships', projectCode] });

  const addMutation = useMutation({
    mutationFn: (payload: ProjectRelationshipCreatePayload) =>
      projectsApi.addRelationship(projectCode, payload),
    onSuccess: () => {
      message.success('关系已建立');
      invalidate();
      setAdding(false);
      addForm.resetFields();
      setSearchQ('');
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) message.error('该关系已存在');
      else if (status === 400) message.error(err?.response?.data?.message ?? '不能建立关系');
      else message.error(err?.response?.data?.message ?? '建立关系失败');
    },
  });

  const [cancelling, setCancelling] = useState<ProjectRelationshipItem | null>(null);
  const [cancelForm] = Form.useForm<{ change_reason: string }>();

  const deleteMutation = useMutation({
    mutationFn: ({ relationship_id, reason }: { relationship_id: number; reason: string }) =>
      projectsApi.deleteRelationship(projectCode, relationship_id, reason),
    onSuccess: () => {
      message.success('关系已取消，历史已保留');
      setCancelling(null);
      cancelForm.resetFields();
      invalidate();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '删除失败'),
  });

  const submitAdd = async () => {
    const v = await addForm.validateFields();
    addMutation.mutate(v);
  };

  const columns = [
    {
      title: '方向',
      dataIndex: 'direction',
      width: 90,
      render: (d: string) =>
        d === 'outgoing' ? <Tag color="blue">主动</Tag> : <Tag color="gold">被动</Tag>,
    },
    {
      title: '关系',
      key: 'relation',
      width: 110,
      render: (_: unknown, row: ProjectRelationshipItem) => <Tag>{relationLabel(row)}</Tag>,
    },
    {
      title: '对端项目',
      dataIndex: 'other_project_code',
      width: 170,
      render: (code: string) => <EntityCodeLink type="project" code={code} />,
    },
    { title: '对端项目名', dataIndex: 'other_project_name', ellipsis: true },
    { title: '备注', dataIndex: 'notes', ellipsis: true, render: (v?: string | null) => v ?? '—' },
    {
      title: '建立时间',
      dataIndex: 'created_at',
      width: 150,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_: unknown, row: ProjectRelationshipItem) => (
        <PermissionGuard permission="project:update">
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            loading={deleteMutation.isPending}
            onClick={() => { cancelForm.resetFields(); setCancelling(row); }}
          >
            取消关系
          </Button>
        </PermissionGuard>
      ),
    },
  ];

  return (
    <Card
      title="项目关系（合并 / 拆分 / 衍生 / 依赖）"
      extra={
        <PermissionGuard permission="project:update">
          <Button
            type="primary"
            icon={<ApartmentOutlined />}
            onClick={() => {
              setAdding(true);
              addForm.resetFields();
            }}
          >
            新建关系
          </Button>
        </PermissionGuard>
      }
    >
      <Table<ProjectRelationshipItem>
        size="middle"
        rowKey={(r) => r.relationship_id}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">该项目尚无关系</Text> }}
      />

      <Modal
        open={adding}
        title="新建项目关系"
        okText="建立"
        onCancel={() => {
          setAdding(false);
          addForm.resetFields();
          setSearchQ('');
        }}
        onOk={submitAdd}
        confirmLoading={addMutation.isPending}
        destroyOnClose
        width={640}
      >
        <Form name="relationship-create" form={addForm} layout="vertical">
          <Form.Item
            label="关系类型"
            name="relationship_type"
            rules={[{ required: true, message: '必选' }]}
            tooltip="SMP §11.4-11.6；以本项目为主动方描述"
          >
            <Select
              options={PROJECT_RELATIONSHIP_TYPE_OPTIONS.map((o) => ({
                value: o.value,
                label: `本项目 ${o.outLabel} …`,
              }))}
            />
          </Form.Item>
          <Form.Item
            label="对端项目"
            name="to_project_code"
            rules={[{ required: true, message: '必填' }]}
            tooltip="搜索 CMAB-PRJ-YYYY-NNNN 或项目名称"
          >
            <AutoComplete
              placeholder="搜索项目编码或名称..."
              onSearch={setSearchQ}
              options={(searchHits?.results.project.items ?? []).map((h) => ({
                value: h.code,
                label: (
                  <Space>
                    <Text code style={{ fontSize: 12 }}>{h.code}</Text>
                    <Text>{h.name}</Text>
                  </Space>
                ),
              }))}
              filterOption={false}
            />
          </Form.Item>
          <Form.Item label="建立原因" name="change_reason" rules={[{ required: true, min: 5, max: 2000, message: '请填写至少5个字符的原因' }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal title="确认取消项目关系" open={!!cancelling} okText="确认取消" cancelText="返回"
        confirmLoading={deleteMutation.isPending} onCancel={() => setCancelling(null)}
        onOk={async () => {
          const values = await cancelForm.validateFields();
          if (cancelling) deleteMutation.mutate({ relationship_id: cancelling.relationship_id, reason: values.change_reason });
        }}>
        <p>取消后保留原关系和操作历史，可重新建立关系。</p>
        <Form name="relationship-cancel" form={cancelForm} layout="vertical">
          <Form.Item name="change_reason" label="取消原因" rules={[{ required: true, min: 5, max: 2000, message: '请填写至少5个字符的原因' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
