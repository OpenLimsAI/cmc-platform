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
import { assetsApi } from '@/api/assets';
import { searchApi } from '@/api/search';
import type {
  AssetSubstanceLink,
  AssetSubstanceLinkCreatePayload,
  ComponentRole,
} from '@/api/types';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { COMPONENT_ROLE_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  assetCode: string;
  assetStatus?: string;  // terminated 时禁用绑定按钮
}

interface AddForm {
  substance_code: string;
  component_role: ComponentRole;
  is_active_ingredient?: boolean;
  notes?: string;
}

export function AssetSubstanceTab({ assetCode, assetStatus }: Props) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [unlinking, setUnlinking] = useState<AssetSubstanceLink | null>(null);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [addForm] = Form.useForm<AddForm>();
  const [unlinkForm] = Form.useForm<{ reason?: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ['asset-substances', assetCode, includeDeleted],
    queryFn: () => assetsApi.listSubstances(assetCode, includeDeleted),
  });

  const { data: searchHits } = useQuery({
    queryKey: ['search-substance-for-asset', searchQ],
    queryFn: () => searchApi.search(searchQ, 'substance', 20),
    enabled: adding && searchQ.trim().length > 0,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['asset-substances', assetCode] });
    queryClient.invalidateQueries({ queryKey: ['asset-audit-logs', assetCode] });
  };

  const linkMutation = useMutation({
    mutationFn: (payload: AssetSubstanceLinkCreatePayload) =>
      assetsApi.linkSubstance(assetCode, payload),
    onSuccess: () => {
      message.success('物质组分已绑定');
      invalidate();
      setAdding(false);
      addForm.resetFields();
      setSearchQ('');
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      if (status === 409) message.error('该物质在此组分角色下已绑定');
      else if (status === 400) message.error(err?.response?.data?.message ?? '不能新建关联');
      else if (status === 404) message.error('物质不存在或已删除');
      else message.error(err?.response?.data?.message ?? '绑定失败');
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: ({
      substance_code,
      component_role,
      reason,
    }: {
      substance_code: string;
      component_role: string;
      reason?: string;
    }) => assetsApi.unlinkSubstance(assetCode, substance_code, component_role, reason),
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
      component_role: unlinking.component_role,
      reason: v.reason,
    });
  };

  const disabledByTerminated = assetStatus === 'terminated';

  const columns = [
    {
      title: '物质编码',
      dataIndex: 'substance_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="substance" code={code} />,
    },
    { title: '名称', dataIndex: 'substance_preferred_name', ellipsis: true },
    {
      title: '物质状态',
      dataIndex: 'substance_status',
      width: 100,
      render: (s: string) => <StatusBadge type="substance" status={s} />,
    },
    {
      title: '组分角色',
      dataIndex: 'component_role',
      width: 110,
      render: (r: string) => {
        const def = COMPONENT_ROLE_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? r}</Tag>;
      },
    },
    {
      title: '活性成分',
      dataIndex: 'is_active_ingredient',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : '—'),
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
      render: (_: unknown, row: AssetSubstanceLink) =>
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
          <span>关联物质（组分）</span>
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
              addForm.setFieldsValue({
                component_role: 'main_component',
                is_active_ingredient: true,
              });
            }}
          >
            绑定物质
          </Button>
        </PermissionGuard>
      }
    >
      <Table<AssetSubstanceLink>
        size="middle"
        rowKey={(r) => `${r.substance_code}:${r.component_role}`}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">暂无关联物质组分</Text> }}
      />

      <Modal
        open={adding}
        title="为资产绑定物质组分"
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
              options={(searchHits ?? []).map((h) => ({
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
            label="组分角色"
            name="component_role"
            rules={[{ required: true }]}
            tooltip="DM-MDM-001 §11.3 定义 6 种组分角色"
          >
            <Select
              options={COMPONENT_ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
          </Form.Item>
          <Form.Item name="is_active_ingredient" valuePropName="checked">
            <Checkbox>活性成分（is_active_ingredient）</Checkbox>
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
            ? `取消引用：${unlinking.substance_code} (${unlinking.component_role})`
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
