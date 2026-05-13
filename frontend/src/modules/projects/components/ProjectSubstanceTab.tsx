import { useState } from 'react';
import {
  AutoComplete,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, LinkOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { projectsApi } from '@/api/projects';
import { searchApi } from '@/api/search';
import type {
  ProjectSubstanceLink,
  ProjectSubstanceLinkCreatePayload,
  RelationType,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { RELATION_TYPE_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  projectCode: string;
}

interface AddForm {
  substance_code: string;
  relation_type: RelationType;
  is_primary?: boolean;
  notes?: string;
}

export function ProjectSubstanceTab({ projectCode }: Props) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [unlinking, setUnlinking] = useState<ProjectSubstanceLink | null>(null);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [addForm] = Form.useForm<AddForm>();
  const [unlinkForm] = Form.useForm<{ reason?: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['project-substances', projectCode, includeDeleted],
    queryFn: () => projectsApi.listSubstances(projectCode, includeDeleted),
  });

  // 添加 Modal 内的物质搜索（types=substance）
  const { data: searchHits } = useQuery({
    queryKey: ['search-substance', searchQ],
    queryFn: () => searchApi.search(searchQ, 'substance', 20),
    enabled: adding && searchQ.trim().length > 0,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['project-substances', projectCode] });
    queryClient.invalidateQueries({ queryKey: ['project-audit-logs', projectCode] });
  };

  const linkMutation = useMutation({
    mutationFn: (payload: ProjectSubstanceLinkCreatePayload) =>
      projectsApi.linkSubstance(projectCode, payload),
    onSuccess: () => {
      message.success('物质已绑定');
      invalidate();
      setAdding(false);
      addForm.resetFields();
      setSearchQ('');
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) message.error('该物质在此关联类型下已与项目绑定');
      else if (status === 400) message.error(err?.response?.data?.message ?? '该物质不能新建关联');
      else if (status === 404) message.error('物质不存在或已删除');
      else message.error(err?.response?.data?.message ?? '绑定失败');
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: ({
      substance_code,
      relation_type,
      reason,
    }: {
      substance_code: string;
      relation_type: string;
      reason?: string;
    }) => projectsApi.unlinkSubstance(projectCode, substance_code, relation_type, reason),
    onSuccess: () => {
      message.success('已取消引用');
      invalidate();
      setUnlinking(null);
      unlinkForm.resetFields();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '取消引用失败'),
  });

  const submitAdd = async () => {
    const v = await addForm.validateFields();
    linkMutation.mutate(v);
  };

  const submitUnlink = async () => {
    const v = await unlinkForm.validateFields();
    if (!unlinking) return;
    unlinkMutation.mutate({
      substance_code: unlinking.substance_code,
      relation_type: unlinking.relation_type,
      reason: v.reason,
    });
  };

  const columns = [
    {
      title: '物质编码',
      dataIndex: 'substance_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="substance" code={code} />,
    },
    {
      title: '名称',
      dataIndex: 'substance_preferred_name',
      ellipsis: true,
    },
    {
      title: '物质状态',
      dataIndex: 'substance_status',
      width: 100,
      render: (s: string) => <StatusBadge type="substance" status={s} />,
    },
    {
      title: '关联类型',
      dataIndex: 'relation_type',
      width: 110,
      render: (r: string) => {
        const def = RELATION_TYPE_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? r}</Tag>;
      },
    },
    {
      title: '主要',
      dataIndex: 'is_primary',
      width: 70,
      render: (v: boolean) => (v ? <Tag color="gold">主</Tag> : '—'),
    },
    {
      title: '绑定时间',
      dataIndex: 'created_at',
      width: 150,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '取消时间',
      dataIndex: 'deleted_at',
      width: 150,
      render: (v?: string | null) =>
        v ? <Text type="danger">{dayjs(v).format('YYYY-MM-DD HH:mm')}</Text> : '—',
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: unknown, row: ProjectSubstanceLink) =>
        row.deleted_at ? (
          <Text type="secondary">已取消</Text>
        ) : (
          <PermissionGuard permission="project:update">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                setUnlinking(row);
                unlinkForm.resetFields();
              }}
            >
              取消
            </Button>
          </PermissionGuard>
        ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <span>关联物质</span>
          <Switch
            size="small"
            checked={includeDeleted}
            onChange={setIncludeDeleted}
            checkedChildren="含已取消"
            unCheckedChildren="仅活动"
          />
        </Space>
      }
      extra={
        <PermissionGuard permission="project:update">
          <Button
            type="primary"
            icon={<LinkOutlined />}
            onClick={() => {
              setAdding(true);
              addForm.resetFields();
              addForm.setFieldsValue({ relation_type: 'primary', is_primary: true });
            }}
          >
            绑定物质
          </Button>
        </PermissionGuard>
      }
    >
      <Table<ProjectSubstanceLink>
        size="middle"
        rowKey={(r) => `${r.substance_code}:${r.relation_type}`}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">暂无关联物质</Text> }}
      />

      <Modal
        open={adding}
        title="绑定物质到项目"
        okText="绑定"
        onCancel={() => {
          setAdding(false);
          addForm.resetFields();
          setSearchQ('');
        }}
        onOk={submitAdd}
        confirmLoading={linkMutation.isPending}
        destroyOnClose
        width={640}
      >
        <Form form={addForm} layout="vertical">
          <Form.Item
            label="物质编码"
            name="substance_code"
            rules={[{ required: true, message: '必填' }]}
            tooltip="输入物质编码或名称查询；选择下拉项后会自动填入 SUB-XXXXXXX"
          >
            <AutoComplete
              placeholder="搜索 SUB-XXXXXXX、preferred name 或 INN..."
              onSearch={setSearchQ}
              options={(searchHits?.results.substance.items ?? []).map((h) => ({
                value: h.code,
                label: (
                  <Space>
                    <Text code style={{ fontSize: 12 }}>{h.code}</Text>
                    <Text>{h.name}</Text>
                    {h.snippet && <Text type="secondary">· {h.snippet}</Text>}
                  </Space>
                ),
              }))}
              filterOption={false}
            />
          </Form.Item>
          <Form.Item
            label="关联类型"
            name="relation_type"
            rules={[{ required: true }]}
            tooltip="DM-MDM-001 §11.2 定义五种引用类型"
          >
            <Select
              options={RELATION_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
          </Form.Item>
          <Form.Item name="is_primary" valuePropName="checked">
            <Checkbox>标记为主关联（is_primary）</Checkbox>
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={unlinking !== null}
        title={
          unlinking
            ? `取消引用：${unlinking.substance_code} (${unlinking.relation_type})`
            : ''
        }
        okText="确认取消"
        okButtonProps={{ danger: true }}
        cancelText="返回"
        onCancel={() => {
          setUnlinking(null);
          unlinkForm.resetFields();
        }}
        onOk={submitUnlink}
        confirmLoading={unlinkMutation.isPending}
        destroyOnClose
      >
        <Form form={unlinkForm} layout="vertical">
          <Form.Item label="取消原因（写入审计；可选）" name="reason">
            <Input.TextArea rows={3} placeholder="说明取消引用的原因" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
