import { useMemo, useState } from 'react';
import { Button, Card, Form, Input, Modal, Select, Space, Spin, Switch, Table, Tag, Typography, message } from 'antd';
import { DeleteOutlined, EditOutlined, LinkOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  targetsApi,
  type MoleculeTargetLink,
  type MoleculeTargetLinkCreatePayload,
  type MoleculeTargetRole,
} from '@/api/targets';
import { substancesApi } from '@/api/substances';
import { useAuthStore } from '@/stores/authStore';
import { MOLECULE_TARGET_ROLE_OPTIONS } from '../constants';

const { Text } = Typography;

const ACTION_TYPE_SUGGESTIONS = ['INHIBITOR', 'ANTAGONIST', 'AGONIST', 'BINDING AGENT', 'BLOCKER', 'MODULATOR', 'DEGRADER', 'OTHER'];

interface Props {
  /** 'target'：在靶点详情页，列出/维护它的分子；'substance'：在物质详情页，列出/维护它的靶点 */
  mode: 'target' | 'substance';
  code: string; // targetCode 或 substanceCode
}

/**
 * 分子↔靶点关联面板（ref.molecule_target），靶点详情页 / 物质详情页共用。
 * 关系角色：抗体结合靶点 / 载荷作用靶点（ADC）/ 其他；MoA、作用类型、表位/结构域人工或预填脚本给出。
 */
export function MoleculeTargetPanel({ mode, code }: Props) {
  const queryClient = useQueryClient();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const canEdit = hasPermission('target:update');
  const canRead = hasPermission('target:read');

  const queryKey = mode === 'target' ? ['target-molecules', code] : ['substance-targets', code];
  const { data: links = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => (mode === 'target' ? targetsApi.molecules(code) : targetsApi.targetsOfMolecule(code)),
    enabled: !!code && canRead,
  });

  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<MoleculeTargetLink | null>(null);
  const [removing, setRemoving] = useState<MoleculeTargetLink | null>(null);
  const [removeReason, setRemoveReason] = useState('');
  const [addForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [otherSearch, setOtherSearch] = useState('');

  // 选"对面"的实体：靶点页选物质，物质页选靶点
  const { data: otherOptions = [], isFetching: searching } = useQuery({
    queryKey: ['mt-panel-other', mode, otherSearch],
    queryFn: async () => {
      if (mode === 'target') {
        const r = await substancesApi.list({ q: otherSearch || undefined, page_size: 20 });
        return r.items.map((s) => ({ value: s.substance_code, label: `${s.substance_code} · ${s.preferred_name}${s.inn ? `（${s.inn}）` : ''}` }));
      }
      const r = await targetsApi.list({ q: otherSearch || undefined, page_size: 20 });
      return r.items.map((t) => ({
        value: t.target_code,
        label: `${t.target_code} · ${t.target_name}${t.uniprot_id ? `（${t.uniprot_id}）` : ''}${t.cd_antigen_names?.length ? ` ${t.cd_antigen_names.join('/')}` : ''}`,
      }));
    },
    enabled: addOpen,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['target-molecules'] });
    queryClient.invalidateQueries({ queryKey: ['substance-targets'] });
    queryClient.invalidateQueries({ queryKey: ['target-audit-logs'] });
  };

  const addMutation = useMutation({
    mutationFn: (v: { other: string; relation_role: MoleculeTargetRole } & Omit<MoleculeTargetLinkCreatePayload, 'substance_code' | 'relation_role'>) => {
      const { other, ...rest } = v;
      const targetCode = mode === 'target' ? code : other;
      const substanceCode = mode === 'target' ? other : code;
      return targetsApi.addMolecule(targetCode, { substance_code: substanceCode, ...rest });
    },
    onSuccess: () => {
      message.success('已建立关联');
      setAddOpen(false);
      addForm.resetFields();
      invalidate();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '关联失败'),
  });

  const editMutation = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      targetsApi.updateMolecule(editing!.target_code, editing!.substance_code, editing!.relation_role, v),
    onSuccess: () => {
      message.success('关联已更新');
      setEditing(null);
      invalidate();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '更新失败'),
  });

  const removeMutation = useMutation({
    mutationFn: () => targetsApi.removeMolecule(removing!.target_code, removing!.substance_code, removing!.relation_role, removeReason),
    onSuccess: () => {
      message.success('已取消关联（软删，可审计）');
      setRemoving(null);
      setRemoveReason('');
      invalidate();
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '取消关联失败'),
  });

  const columns = useMemo(
    () => [
      mode === 'target'
        ? {
            title: '分子（物质）',
            key: 'substance',
            width: 220,
            render: (_: unknown, r: MoleculeTargetLink) => (
              <Link to={`/substances/${encodeURIComponent(r.substance_code)}`}>
                {r.substance_code}
                {r.substance_name ? ` · ${r.substance_name}` : ''}
              </Link>
            ),
          }
        : {
            title: '靶点',
            key: 'target',
            width: 240,
            render: (_: unknown, r: MoleculeTargetLink) => (
              <Link to={`/targets/${encodeURIComponent(r.target_code)}`}>
                {r.target_code} · {r.target_name}
              </Link>
            ),
          },
      {
        title: '关系',
        dataIndex: 'relation_role',
        key: 'relation_role',
        width: 130,
        render: (v: MoleculeTargetRole) => {
          const def = MOLECULE_TARGET_ROLE_OPTIONS.find((o) => o.value === v);
          return <Tag color={def?.color}>{def?.label ?? v}</Tag>;
        },
      },
      { title: '作用机制（MoA）', dataIndex: 'moa', key: 'moa', ellipsis: true, render: (v: string | null) => v ?? '—' },
      { title: '作用类型', dataIndex: 'action_type', key: 'action_type', width: 130, render: (v: string | null) => v ?? '—' },
      { title: '表位 / 结构域', dataIndex: 'binding_epitope_or_domain', key: 'epi', ellipsis: true, render: (v: string | null) => v ?? '—' },
      {
        title: '待确认',
        dataIndex: 'needs_confirm',
        key: 'needs_confirm',
        width: 80,
        render: (v: boolean) => (v ? <Tag color="orange">是</Tag> : <Tag>否</Tag>),
      },
      ...(canEdit
        ? [
            {
              title: '操作',
              key: 'ops',
              width: 130,
              render: (_: unknown, r: MoleculeTargetLink) => (
                <Space size="small">
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditing(r);
                      editForm.setFieldsValue({
                        moa: r.moa ?? undefined,
                        action_type: r.action_type ?? undefined,
                        binding_epitope_or_domain: r.binding_epitope_or_domain ?? undefined,
                        needs_confirm: r.needs_confirm,
                        notes: r.notes ?? undefined,
                        change_reason: undefined,
                      });
                    }}
                  />
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setRemoving(r)} />
                </Space>
              ),
            },
          ]
        : []),
    ],
    [mode, canEdit, editForm],
  );

  if (!canRead) return null;

  return (
    <Card
      size="small"
      title={mode === 'target' ? `关联分子（${links.length}）` : `作用靶点（${links.length}）`}
      extra={
        canEdit ? (
          <Button size="small" type="primary" icon={<LinkOutlined />} onClick={() => setAddOpen(true)}>
            {mode === 'target' ? '关联分子' : '关联靶点'}
          </Button>
        ) : (
          <Text type="secondary">需要 target:update 权限才能维护</Text>
        )
      }
    >
      {isLoading ? (
        <Spin />
      ) : (
        <Table<MoleculeTargetLink>
          columns={columns}
          dataSource={links}
          rowKey={(r) => `${r.substance_code}:${r.target_code}:${r.relation_role}`}
          pagination={false}
          size="small"
          locale={{ emptyText: mode === 'target' ? '暂无关联分子' : '暂无关联靶点；点右上「关联靶点」' }}
        />
      )}

      {/* 新建关联 */}
      <Modal
        open={addOpen}
        title={mode === 'target' ? '关联分子到此靶点' : '为此分子关联靶点'}
        onCancel={() => setAddOpen(false)}
        onOk={async () => {
          const v = await addForm.validateFields();
          addMutation.mutate({ ...v, action_type: Array.isArray(v.action_type) ? v.action_type[0] : v.action_type });
        }}
        confirmLoading={addMutation.isPending}
        okText="建立关联"
        width={640}
      >
        <Form form={addForm} layout="vertical" initialValues={{ relation_role: 'antibody_target', needs_confirm: false }}>
          <Form.Item
            name="other"
            label={mode === 'target' ? '分子（物质）' : '靶点'}
            rules={[{ required: true, message: '请选择' }]}
            extra={mode === 'substance' ? '找不到？先去「靶点」新建（输 UniProt 号一键拉取）' : undefined}
          >
            <Select
              showSearch
              filterOption={false}
              onSearch={setOtherSearch}
              loading={searching}
              options={otherOptions}
              placeholder={mode === 'target' ? '按编码 / 名称 / INN 搜索物质' : '按编码 / 名称 / UniProt / CD 号搜索靶点'}
              notFoundContent={searching ? <Spin size="small" /> : '无匹配'}
            />
          </Form.Item>
          <Form.Item name="relation_role" label="关系" rules={[{ required: true }]}>
            <Select options={MOLECULE_TARGET_ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="moa" label="作用机制（MoA）">
            <Input placeholder="如 Interleukin-23 inhibitor" />
          </Form.Item>
          <Form.Item name="action_type" label="作用类型">
            <Select allowClear showSearch mode="tags" maxCount={1} options={ACTION_TYPE_SUGGESTIONS.map((a) => ({ value: a, label: a }))} placeholder="INHIBITOR / BINDING AGENT …" />
          </Form.Item>
          <Form.Item name="binding_epitope_or_domain" label="结合表位 / 结构域 / 亚基">
            <Input placeholder="如 p19 subunit / domain IV / Ig-like V-type" />
          </Form.Item>
          <Form.Item name="needs_confirm" label="需人工确认" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑关联属性 */}
      <Modal
        open={!!editing}
        title={editing ? `编辑关联：${editing.substance_code} ↔ ${editing.target_code}` : ''}
        onCancel={() => setEditing(null)}
        onOk={async () => {
          const v = await editForm.validateFields();
          editMutation.mutate({ ...v, action_type: Array.isArray(v.action_type) ? v.action_type[0] : v.action_type });
        }}
        confirmLoading={editMutation.isPending}
        okText="保存"
        width={640}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="moa" label="作用机制（MoA）">
            <Input />
          </Form.Item>
          <Form.Item name="action_type" label="作用类型">
            <Input placeholder="INHIBITOR / BINDING AGENT …" />
          </Form.Item>
          <Form.Item name="binding_epitope_or_domain" label="结合表位 / 结构域 / 亚基">
            <Input />
          </Form.Item>
          <Form.Item name="needs_confirm" label="需人工确认" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="change_reason" label="变更原因" rules={[{ required: true, min: 5, message: '至少 5 个字符' }]}>
            <Input.TextArea rows={2} placeholder="为什么改（写入审计）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 取消关联 */}
      <Modal
        open={!!removing}
        title={removing ? `取消关联：${removing.substance_code} ↔ ${removing.target_code}（${removing.relation_role}）` : ''}
        onCancel={() => setRemoving(null)}
        onOk={() => {
          if (removeReason.trim().length < 5) {
            message.warning('请填写原因（至少 5 个字符）');
            return;
          }
          removeMutation.mutate();
        }}
        confirmLoading={removeMutation.isPending}
        okButtonProps={{ danger: true }}
        okText="确认取消关联"
      >
        <p>软删除：关联记录保留并可审计追溯；同一分子/靶点/关系日后可重新关联。</p>
        <Input.TextArea rows={2} value={removeReason} onChange={(e) => setRemoveReason(e.target.value)} placeholder="原因（必填，≥5 字符）" />
      </Modal>
    </Card>
  );
}
