import { useEffect } from 'react';
import { Breadcrumb, Button, Card, Form, Input, Space, Spin, Typography, message } from 'antd';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { targetsApi, type TargetUpdatePayload } from '@/api/targets';
import { TargetFormFields } from '../components/TargetFormFields';
import { UniprotInfoPanel } from '../components/UniprotInfoPanel';

const { Title, Text } = Typography;

export function TargetEditPage() {
  const { code = '' } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const { data: t, isLoading } = useQuery({
    queryKey: ['target', code],
    queryFn: () => targetsApi.get(code),
    enabled: !!code,
  });

  useEffect(() => {
    if (t) {
      form.setFieldsValue({
        uniprot_id: t.uniprot_id ?? undefined,
        target_name: t.target_name,
        gene_symbol: t.gene_symbol ?? undefined,
        organism: t.organism ?? undefined,
        aliases: t.aliases ?? [],
        description: t.description ?? undefined,
        notes: t.notes ?? undefined,
      });
    }
  }, [t, form]);

  const mutation = useMutation({
    mutationFn: (payload: TargetUpdatePayload) => targetsApi.update(code, payload),
    onSuccess: () => {
      message.success('靶点已更新');
      queryClient.invalidateQueries({ queryKey: ['target', code] });
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      navigate(`/targets/${encodeURIComponent(code)}`);
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.message ?? '更新失败');
    },
  });

  if (isLoading || !t) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }
  const hasUniprot = !!t.uniprot_id;

  const onFinish = async () => {
    const v = await form.validateFields();
    // 有 UniProt 号：标准字段只能靠「重新拉取」改，这里只改备注；无 UniProt 号：兜底字段可改
    const payload: TargetUpdatePayload = hasUniprot
      ? { notes: v.notes || null, change_reason: v.change_reason }
      : {
          target_name: v.target_name,
          gene_symbol: v.gene_symbol || null,
          organism: v.organism || null,
          aliases: v.aliases?.length ? v.aliases : null,
          description: v.description || null,
          notes: v.notes || null,
          change_reason: v.change_reason,
        };
    mutation.mutate(payload);
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <Link to="/targets">靶点</Link> },
          { title: <Link to={`/targets/${encodeURIComponent(code)}`}>{code}</Link> },
          { title: '编辑' },
        ]}
      />
      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          编辑靶点 {t.target_code}
        </Title>
        <Text type="secondary">
          {hasUniprot
            ? 'UniProt 标准字段只读（要更新请在详情页「从 UniProt 重新拉取」）；这里只能改备注。'
            : '无 UniProt 号的兜底靶点：可修改名称/基因/物种/别名/描述。'}
        </Text>
      </Card>
      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 960 }}>
          <TargetFormFields lockAccession fetched={hasUniprot} />
          {hasUniprot && (
            <Card size="small" title="UniProt 标准字段（只读）" style={{ marginBottom: 16 }}>
              <UniprotInfoPanel data={t} compact />
            </Card>
          )}
          <Form.Item
            name="change_reason"
            label="变更原因"
            rules={[{ required: true, min: 5, message: '请填写变更原因（至少 5 个字符）' }]}
          >
            <Input.TextArea rows={2} placeholder="为什么改（写入审计）" maxLength={2000} />
          </Form.Item>
          <Space>
            <Button type="primary" loading={mutation.isPending} onClick={onFinish}>
              保存
            </Button>
            <Button onClick={() => navigate(`/targets/${encodeURIComponent(code)}`)}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
