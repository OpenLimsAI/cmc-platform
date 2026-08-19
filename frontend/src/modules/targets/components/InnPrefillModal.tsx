import { useState } from 'react';
import { Alert, Button, Checkbox, Descriptions, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import { CloudDownloadOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { targetsApi, type InnPrefillCandidate, type InnPrefillResponse, type MoleculeTargetRole } from '@/api/targets';
import { useAuthStore } from '@/stores/authStore';
import { MOLECULE_TARGET_ROLE_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
  substanceCode: string;
  defaultInn?: string | null;
}

interface Row extends InnPrefillCandidate {
  key: string;
  selected: boolean;
}

/**
 * 物质页「按 INN 自动找靶点」：ChEMBL(分子→机制→靶点) → UniProt → 候选表 → 勾选 → 一键建靶点草稿 + 关联 + 快照 + 物质标识符。
 * PoC 结论固化：PROTEIN COMPLEX 亚基提示 UNLIKELY 默认不勾；ADC 载荷靶点标 payload_target；已存在的靶点只建关联。
 */
export function InnPrefillModal({ open, onClose, substanceCode, defaultInn }: Props) {
  const queryClient = useQueryClient();
  const canCreate = useAuthStore((s) => s.hasPermission('target:create'));
  const [inn, setInn] = useState(defaultInn ?? '');
  const [res, setRes] = useState<InnPrefillResponse | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [addXrefs, setAddXrefs] = useState(true);

  const fetchMutation = useMutation({
    mutationFn: (q: string) => targetsApi.prefillInn(q),
    onSuccess: (r) => {
      setRes(r);
      setRows(r.candidates.map((c, i) => ({ ...c, key: `${c.uniprot_id ?? 'x'}-${c.relation_role}-${i}`, selected: c.suggested_selected })));
      if (r.outcome === 'REJECTED_NO_MOLECULE') message.warning(r.user_message ?? 'ChEMBL 查无此 INN');
      else if (r.outcome === 'NEEDS_MANUAL_PICK') message.warning(r.user_message ?? '需人工挑选分子');
      else if (r.outcome === 'ERROR_EXTERNAL_CALL') message.error('外部接口调用失败，请稍后重试');
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '查询失败'),
  });

  const applyMutation = useMutation({
    mutationFn: () =>
      targetsApi.applyInn({
        substance_code: substanceCode,
        inn: res!.inn,
        molecule: res!.molecule,
        links: rows
          .filter((r) => r.selected && r.uniprot_id)
          .map((r) => ({
            uniprot_id: r.uniprot_id!,
            relation_role: r.relation_role,
            moa: r.moa,
            action_type: r.action_type,
            binding_epitope_or_domain: r.binding_epitope_or_domain,
            chembl_mechanism_id: r.chembl_mechanism_id,
            needs_confirm: r.needs_confirm,
            new_target: r.existing ? null : r.new_target,
          })),
        snapshots: res!.snapshots,
        add_substance_xrefs: addXrefs,
      }),
    onSuccess: (r) => {
      const parts = [
        r.created_targets.length ? `新建靶点 ${r.created_targets.map((t) => t.target_code).join('、')}` : null,
        `建立关联 ${r.linked.length} 条`,
        r.xrefs_added.length ? `回填标识符 ${r.xrefs_added.length} 个` : null,
        r.skipped.length ? `跳过 ${r.skipped.length} 项` : null,
      ].filter(Boolean);
      message.success(parts.join('；'), 6);
      if (r.skipped.length) message.info(r.skipped.join('；'), 8);
      queryClient.invalidateQueries({ queryKey: ['substance-targets'] });
      queryClient.invalidateQueries({ queryKey: ['target-molecules'] });
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      queryClient.invalidateQueries({ queryKey: ['substance', substanceCode] });
      onClose();
      setRes(null);
      setRows([]);
    },
    onError: (err: any) => message.error(err?.response?.data?.message ?? '应用失败'),
  });

  const update = (key: string, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const selectedCount = rows.filter((r) => r.selected && r.uniprot_id).length;
  const needsCreate = rows.some((r) => r.selected && !r.existing);

  const columns = [
    {
      title: '选',
      key: 'sel',
      width: 44,
      render: (_: unknown, r: Row) => (
        <Checkbox checked={r.selected} disabled={!r.uniprot_id} onChange={(e) => update(r.key, { selected: e.target.checked })} />
      ),
    },
    {
      title: '靶点（UniProt）',
      key: 'target',
      width: 260,
      render: (_: unknown, r: Row) => (
        <div>
          <div>
            <Text strong>{r.target_name ?? '—'}</Text>
            {r.gene_symbol ? <Text type="secondary"> {r.gene_symbol}</Text> : null}
          </div>
          <Space size={4} wrap>
            {r.uniprot_id ? (
              <a href={`https://www.uniprot.org/uniprotkb/${r.uniprot_id}/entry`} target="_blank" rel="noreferrer">
                {r.uniprot_id}
              </a>
            ) : (
              <Tag color="red">无 UniProt 号</Tag>
            )}
            {r.existing ? (
              <Tag color="green">
                已有 <Link to={`/targets/${encodeURIComponent(r.existing.target_code)}`}>{r.existing.target_code}</Link>
              </Tag>
            ) : (
              <Tag color="blue">将新建草稿</Tag>
            )}
            {r.binding_subunit_hint === 'LIKELY' && <Tag color="gold">结合亚基（可能）</Tag>}
            {r.binding_subunit_hint === 'UNLIKELY' && <Tag>非结合亚基（可能）</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '关系',
      key: 'role',
      width: 150,
      render: (_: unknown, r: Row) => (
        <Select
          size="small"
          style={{ width: 140 }}
          value={r.relation_role}
          onChange={(v: MoleculeTargetRole) => update(r.key, { relation_role: v })}
          options={MOLECULE_TARGET_ROLE_OPTIONS}
        />
      ),
    },
    {
      title: '作用机制 / 类型',
      key: 'moa',
      render: (_: unknown, r: Row) => (
        <div>
          <Input size="small" value={r.moa ?? ''} onChange={(e) => update(r.key, { moa: e.target.value })} placeholder="MoA" />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {r.action_type ?? '—'}
            {r.binding_epitope_or_domain ? ` · ${r.binding_epitope_or_domain}` : ''}
          </Text>
        </div>
      ),
    },
    {
      title: '待确认',
      key: 'nc',
      width: 80,
      render: (_: unknown, r: Row) => (
        <Checkbox checked={r.needs_confirm} onChange={(e) => update(r.key, { needs_confirm: e.target.checked })} title={r.confirm_reason ?? undefined} />
      ),
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={() => {
        onClose();
      }}
      title="按 INN 自动找靶点并关联（ChEMBL → UniProt）"
      width={980}
      footer={[
        <Button key="cancel" onClick={onClose}>
          关闭
        </Button>,
        <Button
          key="apply"
          type="primary"
          disabled={!res || selectedCount === 0 || (needsCreate && !canCreate)}
          loading={applyMutation.isPending}
          onClick={() => applyMutation.mutate()}
        >
          应用（{selectedCount} 条关联{needsCreate ? '，含新建靶点' : ''}）
        </Button>,
      ]}
    >
      <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
        <Input
          placeholder="INN，如 guselkumab / pembrolizumab / trastuzumab deruxtecan"
          value={inn}
          onChange={(e) => setInn(e.target.value)}
          onPressEnter={() => inn.trim() && fetchMutation.mutate(inn.trim())}
        />
        <Button type="primary" icon={<CloudDownloadOutlined />} loading={fetchMutation.isPending} onClick={() => inn.trim() && fetchMutation.mutate(inn.trim())}>
          查询
        </Button>
      </Space.Compact>
      {fetchMutation.isPending && <Alert type="info" showIcon message="正在查询 ChEMBL（分子 → 机制 → 靶点）和 UniProt，通常 5–20 秒…" style={{ marginBottom: 12 }} />}

      {res && res.molecule && (
        <Descriptions size="small" bordered column={3} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="ChEMBL 分子">
            <a href={`https://www.ebi.ac.uk/chembl/explore/compound/${res.molecule.chembl_id}`} target="_blank" rel="noreferrer">
              {res.molecule.chembl_id}
            </a>{' '}
            {res.molecule.pref_name}
          </Descriptions.Item>
          <Descriptions.Item label="类型 / 阶段">
            {res.molecule.molecule_type ?? '—'} · phase {res.molecule.max_phase ?? '—'}
            {res.molecule.first_approval ? ` · 首批 ${res.molecule.first_approval}` : ''}
          </Descriptions.Item>
          <Descriptions.Item label="代号 / 商品名">
            {[...res.molecule.research_codes, ...res.molecule.trade_names].join(', ') || '—'}
          </Descriptions.Item>
        </Descriptions>
      )}
      {res?.warnings.map((w, i) => (
        <Alert key={i} type="warning" showIcon message={w} style={{ marginBottom: 8 }} />
      ))}
      {res && res.outcome === 'NEEDS_MANUAL_PICK' && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 8 }}
          message={res.user_message}
          description={res.chembl_candidates.map((c) => `${c.molecule_chembl_id} ${c.pref_name}（${c.molecule_type}）`).join('；')}
        />
      )}
      {res && res.candidates.length > 0 && (
        <>
          <Table<Row> size="small" columns={columns} dataSource={rows} rowKey="key" pagination={false} />
          <div style={{ marginTop: 10 }}>
            <Checkbox checked={addXrefs} onChange={(e) => setAddXrefs(e.target.checked)}>
              同时把 ChEMBL ID / INN / 商品名回填到物质「标识符」（已有的跳过）
            </Checkbox>
          </div>
          {needsCreate && !canCreate && (
            <Alert type="error" showIcon style={{ marginTop: 8 }} message="勾选项包含需要新建的靶点，但你没有 target:create 权限；请只勾已有靶点或找研发/管理员建靶点。" />
          )}
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            说明：新建的靶点为草稿（UniProt 标准字段自动填好、附 UniProt/ChEMBL 快照），发布请到靶点页；关联默认带"待确认"标记的请人工核对。
          </Text>
        </>
      )}
      {res && res.candidates.length === 0 && res.outcome.startsWith('OK') && (
        <Alert type="info" showIcon message="ChEMBL 有该分子但没有靶点/机制记录，需人工关联。" />
      )}
    </Modal>
  );
}
