import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Input,
  Modal,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  targetsApi,
  type MoleculeTargetLink,
  type TargetAction,
  type TargetSnapshotBrief,
} from '@/api/targets';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { StatusActionsBar } from '@/shared/components/StatusActionsBar';
import {
  MOLECULE_TARGET_ROLE_OPTIONS,
  SNAPSHOT_SOURCE_LABELS,
  TARGET_AVAILABLE_ACTIONS,
  TARGET_LOCATION_OPTIONS,
  TARGET_STATUS_OPTIONS,
  TARGET_TYPE_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function TargetDetailPage() {
  const { code = '' } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [reason, setReason] = useState('');

  const { data: t, isLoading } = useQuery({
    queryKey: ['target', code],
    queryFn: () => targetsApi.get(code),
    enabled: !!code,
  });
  const { data: links = [] } = useQuery({
    queryKey: ['target-molecules', code],
    queryFn: () => targetsApi.molecules(code),
    enabled: !!code,
  });
  const { data: snapshots = [] } = useQuery({
    queryKey: ['target-snapshots', code],
    queryFn: () => targetsApi.snapshots(code),
    enabled: !!code,
  });

  const deleteMutation = useMutation({
    mutationFn: () => targetsApi.delete(code, reason),
    onSuccess: () => {
      message.success('靶点已删除（软删除，审计可追溯）');
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      navigate('/targets');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? '删除失败');
    },
  });

  if (isLoading || !t) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }

  const typeDef = TARGET_TYPE_OPTIONS.find((o) => o.value === t.target_type);
  const locDef = TARGET_LOCATION_OPTIONS.find((o) => o.value === t.target_location);
  const statusDef = TARGET_STATUS_OPTIONS.find((o) => o.value === t.status);

  const linkColumns = [
    {
      title: '分子（物质）',
      dataIndex: 'substance_code',
      key: 'substance_code',
      width: 150,
      render: (c: string, row: MoleculeTargetLink) => (
        <Link to={`/substances/${encodeURIComponent(c)}`}>
          {c}
          {row.substance_name ? ` · ${row.substance_name}` : ''}
        </Link>
      ),
    },
    {
      title: '关系',
      dataIndex: 'relation_role',
      key: 'relation_role',
      width: 130,
      render: (r: string) => {
        const def = MOLECULE_TARGET_ROLE_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color}>{def?.label ?? r}</Tag>;
      },
    },
    { title: '作用机制（MoA）', dataIndex: 'moa', key: 'moa', ellipsis: true, render: (v: string | null) => v ?? '—' },
    { title: '作用类型', dataIndex: 'action_type', key: 'action_type', width: 130, render: (v: string | null) => v ?? '—' },
    {
      title: '表位 / 结构域',
      dataIndex: 'binding_epitope_or_domain',
      key: 'binding_epitope_or_domain',
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '待确认',
      dataIndex: 'needs_confirm',
      key: 'needs_confirm',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="orange">是</Tag> : <Tag>否</Tag>),
    },
  ];

  const snapColumns = [
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 150,
      render: (s: TargetSnapshotBrief['source']) => SNAPSHOT_SOURCE_LABELS[s] ?? s,
    },
    {
      title: '外部 ID',
      dataIndex: 'source_id',
      key: 'source_id',
      width: 140,
      render: (v: string | null, row: TargetSnapshotBrief) =>
        row.source_url ? (
          <a href={row.source_url} target="_blank" rel="noreferrer">
            {v ?? row.source_url}
          </a>
        ) : (
          v ?? '—'
        ),
    },
    { title: '版本', dataIndex: 'source_version', key: 'source_version', width: 140, render: (v: string | null) => v ?? '—' },
    { title: '抓取时间', dataIndex: 'fetched_at', key: 'fetched_at', width: 140, render: (v: string) => <TimeDisplay value={v} /> },
    { title: '许可', dataIndex: 'license', key: 'license', render: (v: string | null) => v ?? '—' },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: <Link to="/targets">靶点</Link> }, { title: t.target_code }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {t.target_code} — {t.target_name} <Tag color={typeDef?.color}>{t.target_type}</Tag>
              <Tag color={locDef?.color}>{t.target_location}</Tag>
              <Tag color={statusDef?.color}>{statusDef?.label ?? t.status}</Tag>
            </Title>
            <Text type="secondary">
              靶点主属性（是什么）；监管/市场状态不在 MDM。草稿需人工核对后发布。
            </Text>
          </div>
          <Space>
            <StatusActionsBar
              actions={TARGET_AVAILABLE_ACTIONS[t.status] ?? []}
              changeStatusFn={async (action, comment) => {
                const d = await targetsApi.changeStatus(code, action as TargetAction, comment);
                return { new_status: d.status };
              }}
              permission="target:approve"
              detailQueryKey={['target', code]}
              listQueryKey={['targets']}
              entityCode={t.target_code}
              entityTypeLabel="靶点"
            />
            <PermissionGuard permission="target:update">
              <Button icon={<EditOutlined />} onClick={() => navigate(`/targets/${encodeURIComponent(code)}/edit`)}>
                编辑
              </Button>
              <Button danger icon={<DeleteOutlined />} onClick={() => setDeleteOpen(true)}>
                删除
              </Button>
            </PermissionGuard>
          </Space>
        </div>
      </Card>

      <Card>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="靶点编码">{t.target_code}</Descriptions.Item>
          <Descriptions.Item label="状态">{statusDef?.label ?? t.status}</Descriptions.Item>
          <Descriptions.Item label="靶点名称" span={2}>
            {t.target_name}
          </Descriptions.Item>
          <Descriptions.Item label="UniProt accession">
            {t.uniprot_id ? (
              <a href={`https://www.uniprot.org/uniprotkb/${t.uniprot_id}/entry`} target="_blank" rel="noreferrer">
                {t.uniprot_id}
              </a>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="基因符号">{t.gene_symbol ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="靶点类型">{t.target_type}</Descriptions.Item>
          <Descriptions.Item label="靶点定位">{t.target_location}</Descriptions.Item>
          <Descriptions.Item label="物种">{t.organism ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="别名 / 次级 accession">
            {t.aliases?.length ? t.aliases.map((a) => <Tag key={a}>{a}</Tag>) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="功能描述" span={2}>
            {t.description ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="备注" span={2}>
            {t.notes ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            <TimeDisplay value={t.created_at} />
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            <TimeDisplay value={t.updated_at} />
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title={`关联分子（${links.length}）`}
        style={{ marginTop: 16 }}
        extra={<Text type="secondary">一期只读展示；关联维护走 API（二期做面板）</Text>}
      >
        <Table<MoleculeTargetLink>
          columns={linkColumns}
          dataSource={links}
          rowKey={(r) => `${r.substance_code}:${r.relation_role}`}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无关联分子' }}
        />
      </Card>

      <Card
        title={`外部源快照（${snapshots.length}）`}
        style={{ marginTop: 16 }}
        extra={<Text type="secondary">UniProt / ChEMBL 抓取原文（裁剪后），append-only，留审计</Text>}
      >
        <Table<TargetSnapshotBrief>
          columns={snapColumns}
          dataSource={snapshots}
          rowKey="snapshot_id"
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无快照（预填脚本 --attach-snapshots 可回填）' }}
        />
      </Card>

      <Modal
        open={deleteOpen}
        title={`删除靶点: ${t.target_code}`}
        onCancel={() => setDeleteOpen(false)}
        onOk={() => {
          if (reason.trim().length < 5) {
            message.warning('请填写删除原因（至少 5 个字符）');
            return;
          }
          deleteMutation.mutate();
        }}
        confirmLoading={deleteMutation.isPending}
        okButtonProps={{ danger: true }}
        okText="确认删除"
      >
        <p>软删除：记录保留并可审计追溯。</p>
        <Input.TextArea
          rows={2}
          placeholder="删除原因（必填，≥5 字符）"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={2000}
        />
      </Modal>
    </div>
  );
}
