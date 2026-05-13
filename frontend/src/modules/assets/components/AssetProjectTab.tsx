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
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, LinkOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { assetsApi } from '@/api/assets';
import { searchApi } from '@/api/search';
import type {
  ProjectAssetLink,
  ProjectAssetLinkFromAssetPayload,
  ProjectAssetRelationType,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { PROJECT_ASSET_RELATION_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  assetCode: string;
  assetStatus?: string;
}

interface AddForm {
  project_code: string;
  relation_type: ProjectAssetRelationType;
  notes?: string;
}

export function AssetProjectTab({ assetCode, assetStatus }: Props) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [unlinking, setUnlinking] = useState<ProjectAssetLink | null>(null);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [addForm] = Form.useForm<AddForm>();
  const [unlinkForm] = Form.useForm<{ reason?: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['asset-projects', assetCode, includeDeleted],
    queryFn: () => assetsApi.listProjects(assetCode, includeDeleted),
  });

  const { data: searchHits } = useQuery({
    queryKey: ['search-project-for-asset', searchQ],
    queryFn: () => searchApi.search(searchQ, 'project', 20),
    enabled: adding && searchQ.trim().length > 0,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['asset-projects', assetCode] });
    queryClient.invalidateQueries({ queryKey: ['asset-audit-logs', assetCode] });
  };

  const linkMutation = useMutation({
    mutationFn: (payload: ProjectAssetLinkFromAssetPayload) =>
      assetsApi.linkProject(assetCode, payload),
    onSuccess: () => {
      message.success('已关联项目');
      invalidate();
      setAdding(false);
      addForm.resetFields();
      setSearchQ('');
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) message.error('该项目已与此资产关联');
      else if (status === 400) message.error(err?.response?.data?.message ?? '不能新建关联');
      else if (status === 404) message.error('项目不存在或已删除');
      else message.error(err?.response?.data?.message ?? '关联失败');
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: ({
      project_code,
      reason,
    }: {
      project_code: string;
      reason?: string;
    }) => assetsApi.unlinkProject(assetCode, project_code, reason),
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
      project_code: unlinking.project_code,
      reason: v.reason,
    });
  };

  const disabledByTerminated = assetStatus === 'terminated';

  const columns = [
    {
      title: '项目编码',
      dataIndex: 'project_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="project" code={code} />,
    },
    { title: '项目名称', dataIndex: 'project_name', ellipsis: true },
    {
      title: '项目状态',
      dataIndex: 'project_status',
      width: 100,
      render: (s: string) => <StatusBadge type="project" status={s} />,
    },
    {
      title: '关联类型',
      dataIndex: 'relation_type',
      width: 110,
      render: (r: string) => {
        const def = PROJECT_ASSET_RELATION_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? r}</Tag>;
      },
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
      render: (_: unknown, row: ProjectAssetLink) =>
        row.deleted_at ? (
          <Text type="secondary">已取消</Text>
        ) : (
          <PermissionGuard permission="asset:update">
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
          <span>关联项目</span>
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
        <PermissionGuard permission="asset:update">
          <Button
            type="primary"
            icon={<LinkOutlined />}
            disabled={disabledByTerminated}
            title={disabledByTerminated ? '已终止资产禁止新建关联' : undefined}
            onClick={() => {
              setAdding(true);
              addForm.resetFields();
              addForm.setFieldsValue({ relation_type: 'primary' });
            }}
          >
            关联项目
          </Button>
        </PermissionGuard>
      }
    >
      <Table<ProjectAssetLink>
        size="middle"
        rowKey={(r) => r.project_code}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">该资产尚未关联任何项目</Text> }}
      />

      <Modal
        open={adding}
        title="为资产关联项目"
        okText="关联"
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
            label="项目编码"
            name="project_code"
            rules={[{ required: true, message: '必填' }]}
          >
            <AutoComplete
              placeholder="搜索 PRJ-YYYY-XXXX 或项目名称..."
              onSearch={setSearchQ}
              options={(searchHits?.results.project.items ?? []).map((h) => ({
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
            tooltip="DM-MDM-001 §11.4；前端建议值，后端无 CHECK"
          >
            <Select
              options={PROJECT_ASSET_RELATION_OPTIONS.map((o) => ({
                value: o.value,
                label: o.label,
              }))}
            />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={unlinking !== null}
        title={unlinking ? `取消引用：${unlinking.project_code}` : ''}
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
