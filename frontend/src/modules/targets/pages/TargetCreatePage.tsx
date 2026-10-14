import { useIdempotentCreate } from '@/shared/hooks/useIdempotentCreate';
import { useState } from 'react';
import { Alert, Breadcrumb, Button, Card, Form, Space, Typography, message } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import {
  targetsApi,
  type TargetCreatePayload,
  type TargetPrefillResponse,
  type TargetSnapshotCreatePayload,
} from '@/api/targets';
import { TargetFormFields } from '../components/TargetFormFields';
import { UniprotInfoPanel } from '../components/UniprotInfoPanel';

const { Title, Text } = Typography;

export function TargetCreatePage() {
  const createOnce = useIdempotentCreate((payload: TargetCreatePayload, key: string) => targetsApi.create(payload, key));
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [prefill, setPrefill] = useState<TargetPrefillResponse | null>(null);
  const [snapshot, setSnapshot] = useState<TargetSnapshotCreatePayload | null>(null);

  // 按 UniProt accession 拉一条 → 全部标准字段进表单（不落库）
  const fetchMutation = useMutation({
    mutationFn: (accession: string) => targetsApi.prefillUniprot(accession),
    onSuccess: (r) => {
      setPrefill(r);
      setSnapshot(r.snapshot);
      form.setFieldsValue({ ...r.form, aliases: r.form.aliases ?? [] });
      if (r.existing) {
        message.warning(`库里已有 ${r.existing.target_code}（${r.existing.target_name}），请改为建立分子-靶点关联`, 8);
      } else {
        message.success(`已从 UniProt 拉取 ${r.accession}，核对无误后保存`);
      }
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? 'UniProt 拉取失败');
    },
  });

  const mutation = useMutation({
    mutationFn: createOnce,
    onSuccess: async (detail) => {
      // 有拉取原文就顺手存快照（失败不阻断，靶点已建成）
      if (snapshot && snapshot.source_id === detail.uniprot_id) {
        try {
          await targetsApi.addSnapshot(detail.target_code, snapshot);
        } catch {
          message.warning('靶点已创建，但 UniProt 快照保存失败（可在详情页「重新拉取」补上）');
        }
      }
      message.success(`靶点 ${detail.target_code} 创建成功（草稿）`);
      navigate(`/targets/${encodeURIComponent(detail.target_code)}`);
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? err?.message ?? '创建失败');
    },
  });

  const onFinish = async () => {
    const v = await form.validateFields();
    const base = prefill && !prefill.existing ? prefill.form : {};
    mutation.mutate({
      ...base,
      target_name: v.target_name || base.target_name || '',
      uniprot_id: v.uniprot_id || null,
      gene_symbol: v.gene_symbol ?? base.gene_symbol ?? null,
      organism: v.organism ?? base.organism ?? 'Homo sapiens',
      aliases: v.aliases?.length ? v.aliases : (base.aliases ?? null),
      description: v.description ?? base.description ?? null,
      notes: v.notes || null,
    });
  };

  const fetched = !!prefill && !prefill.existing;

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[{ title: <Link to="/targets">靶点</Link> }, { title: '新建' }]}
      />
      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          新建靶点
        </Title>
        <Text type="secondary">
          只需填 UniProt accession → 「拉取」→ 核对 → 保存。名称/基因/CD 号/关键词/亚细胞定位/EC 号/结构域/序列信息全部按 UniProt 标准自动带出，人不手填。编码 TGT-NNNNNN 系统生成，新建为草稿。
        </Text>
      </Card>

      {prefill?.existing && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`UniProt ${prefill.accession} 已存在于 ${prefill.existing.target_code}（${prefill.existing.target_name}）`}
          description={
            <span>
              保存会被查重拒绝。请到{' '}
              <Link to={`/targets/${encodeURIComponent(prefill.existing.target_code)}`}>{prefill.existing.target_code}</Link>{' '}
              建立分子-靶点关联，而不是新建。
            </span>
          }
        />
      )}
      {fetched && (
        <Alert
          type={prefill.hints.is_human === false || prefill.hints.is_reviewed === false ? 'warning' : 'success'}
          showIcon
          style={{ marginBottom: 16 }}
          message={`已从 UniProt 拉取 ${prefill.accession}${prefill.hints.redirected_from ? `（由旧号 ${prefill.hints.redirected_from} 重定向）` : ''}`}
          description={
            <>
              {prefill.hints.is_human === false && <div>⚠ 物种 taxId={prefill.hints.tax_id}，不是人源蛋白，请确认是否要录入。</div>}
              {prefill.hints.is_reviewed === false && <div>⚠ TrEMBL 自动注释条目（非 Swiss-Prot 人工审阅），可信度较低。</div>}
              <div>请核对下方 UniProt 信息，无误点「保存」；保存时会一并存下 UniProt 原文快照。</div>
            </>
          }
        />
      )}

      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 960 }} initialValues={{ organism: 'Homo sapiens' }}>
          <TargetFormFields
            onFetchUniprot={(acc) => fetchMutation.mutate(acc)}
            fetching={fetchMutation.isPending}
            fetched={fetched}
          />
          {fetched && (
            <Card size="small" title="UniProt 标准字段（自动带出，只读）" style={{ marginBottom: 16 }}>
              <UniprotInfoPanel data={prefill.form} />
            </Card>
          )}
          <Space>
            <Button type="primary" loading={mutation.isPending} onClick={onFinish} disabled={!!prefill?.existing}>
              保存（草稿）
            </Button>
            <Button onClick={() => navigate('/targets')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
