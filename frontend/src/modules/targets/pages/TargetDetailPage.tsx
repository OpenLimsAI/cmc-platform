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
import { CloudSyncOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { targetsApi, type TargetAction, type TargetSnapshotBrief } from '@/api/targets';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { StatusActionsBar } from '@/shared/components/StatusActionsBar';
import { AuditLogPanel } from '@/shared/components/AuditLogPanel';
import { SNAPSHOT_SOURCE_LABELS, TARGET_AVAILABLE_ACTIONS, TARGET_STATUS_OPTIONS } from '../constants';
import { UniprotInfoPanel } from '../components/UniprotInfoPanel';
import { MoleculeTargetPanel } from '../components/MoleculeTargetPanel';

const { Title, Text } = Typography;

export function TargetDetailPage() {
  const { code = '' } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [refreshOpen, setRefreshOpen] = useState(false);
  const [refreshReason, setRefreshReason] = useState('');

  const { data: t, isLoading } = useQuery({
    queryKey: ['target', code],
    queryFn: () => targetsApi.get(code),
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

  const refreshMutation = useMutation({
    mutationFn: () => targetsApi.refreshUniprot(code, refreshReason),
    onSuccess: (d) => {
      message.success(`已从 UniProt 重新拉取（v${d.uniprot_entry_version ?? '?'}），并追加快照`);
      queryClient.invalidateQueries({ queryKey: ['target', code] });
      queryClient.invalidateQueries({ queryKey: ['target-snapshots', code] });
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      setRefreshOpen(false);
      setRefreshReason('');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? '重新拉取失败');
    },
  });

  if (isLoading || !t) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }

  const statusDef = TARGET_STATUS_OPTIONS.find((o) => o.value === t.status);
  const mfKeywords = (t.keywords ?? []).filter((k) => k.category === 'Molecular function');

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
              {t.target_code} — {t.target_name}{' '}
              {t.cd_antigen_names?.map((c) => (
                <Tag key={c} color="geekblue">{c}</Tag>
              ))}
              {mfKeywords.slice(0, 3).map((k) => (
                <Tag key={k.id ?? k.name} color="blue">{k.name}</Tag>
              ))}
              <Tag color={statusDef?.color}>{statusDef?.label ?? t.status}</Tag>
            </Title>
            <Text type="secondary">
              靶点主属性按 UniProt 标准自动维护；监管/市场状态不在 MDM。草稿需人工核对后发布。
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
              {t.uniprot_id && (
                <Button icon={<CloudSyncOutlined />} onClick={() => setRefreshOpen(true)}>
                  从 UniProt 重新拉取
                </Button>
              )}
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
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="靶点编码">{t.target_code}</Descriptions.Item>
          <Descriptions.Item label="状态">{statusDef?.label ?? t.status}</Descriptions.Item>
          <Descriptions.Item label="靶点名称（UniProt 推荐名）" span={2}>
            {t.target_name}
          </Descriptions.Item>
          <Descriptions.Item label="备注（人工）" span={2}>
            {t.notes ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            <TimeDisplay value={t.created_at} />
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            <TimeDisplay value={t.updated_at} />
          </Descriptions.Item>
        </Descriptions>
        <UniprotInfoPanel data={t} />
      </Card>

      <div style={{ marginTop: 16 }}>
        <MoleculeTargetPanel mode="target" code={code} />
      </div>

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

      <Card title="审计历史" style={{ marginTop: 16 }}>
        <AuditLogPanel
          queryKey={['target-audit-logs', code]}
          loadFn={(page, page_size, include_children) => targetsApi.auditLogs(code, { page, page_size, include_children })}
          tableLabels={{ target: '靶点主表', molecule_target: '分子-靶点关联' }}
        />
      </Card>

      <Modal
        open={refreshOpen}
        title={`从 UniProt 重新拉取: ${t.uniprot_id}`}
        onCancel={() => setRefreshOpen(false)}
        onOk={() => {
          if (refreshReason.trim().length < 5) {
            message.warning('请填写变更原因（至少 5 个字符）');
            return;
          }
          refreshMutation.mutate();
        }}
        confirmLoading={refreshMutation.isPending}
        okText="拉取并覆盖"
      >
        <p>按当前 accession 重新抓取 UniProt，整体覆盖名称/基因/CD 号/关键词/定位/结构域/序列等标准字段（备注与状态不变），并追加一条新快照。</p>
        <Input.TextArea
          rows={2}
          placeholder="变更原因（必填，≥5 字符），如：UniProt 条目更新到 v210"
          value={refreshReason}
          onChange={(e) => setRefreshReason(e.target.value)}
          maxLength={2000}
        />
      </Modal>

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
