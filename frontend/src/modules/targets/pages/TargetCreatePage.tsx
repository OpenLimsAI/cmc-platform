import { Breadcrumb, Button, Card, Form, Space, Typography, message } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { targetsApi, type TargetCreatePayload } from '@/api/targets';
import { TargetFormFields } from '../components/TargetFormFields';

const { Title, Text } = Typography;

export function TargetCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const mutation = useMutation({
    mutationFn: (payload: TargetCreatePayload) => targetsApi.create(payload),
    onSuccess: (detail) => {
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
          编码 TGT-NNNNNN 由系统生成；新建为草稿，人工核对后在详情页「发布」。批量录入请先跑预填脚本得到 summary.md 对照填写。
        </Text>
      </Card>
      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 880 }} initialValues={{ organism: 'Homo sapiens' }}>
          <TargetFormFields />
          <Space>
            <Button type="primary" loading={mutation.isPending} onClick={onFinish}>
              保存（草稿）
            </Button>
            <Button onClick={() => navigate('/targets')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
