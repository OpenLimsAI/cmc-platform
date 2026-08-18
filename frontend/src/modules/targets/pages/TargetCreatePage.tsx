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

const { Title, Text } = Typography;

export function TargetCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [prefill, setPrefill] = useState<TargetPrefillResponse | null>(null);
  const [snapshot, setSnapshot] = useState<TargetSnapshotCreatePayload | null>(null);

  // 按 UniProt accession 拉一条 → 填表单（不落库）
  const fetchMutation = useMutation({
    mutationFn: (accession: string) => targetsApi.prefillUniprot(accession),
    onSuccess: (r) => {
      setPrefill(r);
      setSnapshot(r.snapshot);
      form.setFieldsValue({
        target_name: r.form.target_name,
        uniprot_id: r.form.uniprot_id,
        gene_symbol: r.form.gene_symbol,
        organism: r.form.organism,
        aliases: r.form.aliases ?? [],
        target_type: r.form.target_type,
        target_location: r.form.target_location,
        description: r.form.description,
      });
      if (r.existing) {
        message.warning(`库里已有 ${r.existing.target_code}（${r.existing.target_name}），保存会被拒绝，请改为建立分子-靶点关联`, 8);
      } else {
        message.success(`已从 UniProt 拉取 ${r.accession}，请核对类型/定位后保存`);
      }
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? 'UniProt 拉取失败');
    },
  });

  const mutation = useMutation({
    mutationFn: (payload: TargetCreatePayload) => targetsApi.create(payload),
    onSuccess: async (detail) => {
      // 有拉取原文就顺手存快照（失败不阻断，靶点已建成）
      if (snapshot && snapshot.source_id === detail.uniprot_id) {
        try {
          await targetsApi.addSnapshot(detail.target_code, snapshot);
        } catch {
          message.warning('靶点已创建，但 UniProt 快照保存失败（可稍后用脚本回填）');
        }
      }
      message.success(`靶点 ${detail.target_code} 创建成功（草稿）`);
      navigate(`/targets/${encodeURIComponent(detail.target_code)}`);
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? '创建失败');
    },
  });

  const onFinish = async () => {
    const v = await form.validateFields();
    mutation.mutate({
      target_name: v.target_name,
      uniprot_id: v.uniprot_id || null,
      gene_symbol: v.gene_symbol || null,
      organism: v.organism || 'Homo sapiens',
      aliases: v.aliases?.length ? v.aliases : null,
      target_type: v.target_type,
      target_location: v.target_location,
      description: v.description || null,
      notes: v.notes || null,
    });
  };

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
          最省事的填法：只填 UniProt accession → 点「拉取」→ 核对类型/定位 → 保存。编码 TGT-NNNNNN 由系统生成，新建为草稿，详情页「发布」。
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
      {prefill && !prefill.existing && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={`已从 UniProt 拉取 ${prefill.accession}（${prefill.hints.entry_type ?? ''}，版本 ${prefill.hints.entry_version ?? '?'}，${prefill.hints.sequence_length ?? '?'} aa）`}
          description={
            prefill.hints.is_human === false
              ? `注意：物种 tax_id=${prefill.hints.tax_id}，不是人源蛋白，请确认是否要录入。`
              : '名称/基因/别名/功能描述已带出；类型与定位是启发式建议，依据显示在字段下方，请人工确认。保存时会一并存下 UniProt 原文快照。'
          }
        />
      )}

      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 880 }} initialValues={{ organism: 'Homo sapiens' }}>
          <TargetFormFields
            onFetchUniprot={(acc) => fetchMutation.mutate(acc)}
            fetching={fetchMutation.isPending}
            hints={prefill?.hints ?? null}
          />
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
