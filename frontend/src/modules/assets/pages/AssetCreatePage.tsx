import {
  Breadcrumb,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Select,
  Space,
  Typography,
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { assetsApi } from '@/api/assets';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type { AssetCreatePayload } from '@/api/types';
import { ASSET_PHASE_OPTIONS, ASSET_TYPE_OPTIONS } from '../constants';

const { Title } = Typography;

interface FormValues {
  internal_name: string;
  trade_name?: string;
  inn_name?: string;
  asset_type: AssetCreatePayload['asset_type'];
  current_phase?: AssetCreatePayload['current_phase'];
  therapeutic_area?: string;
  indication?: string;
  dosage_form?: string;
  strength?: string;
  route_of_administration?: string;
  is_commercial?: boolean;
  description?: string;
  notes?: string;
}

export function AssetCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();

  const createMutation = useMutation({
    mutationFn: (payload: AssetCreatePayload) => assetsApi.create(payload),
    onSuccess: (detail) => {
      message.success(`资产已创建：${detail.asset_code}`);
      navigate(`/assets/${encodeURIComponent(detail.asset_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      message.error(err?.response?.data?.message ?? '创建失败');
    },
  });

  const onFinish = (values: FormValues) => {
    createMutation.mutate(values as AssetCreatePayload);
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/assets')}>资产</a> },
          { title: '新建资产' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          新建资产
        </Title>
        <p style={{ color: '#8c8c8c', marginTop: -8 }}>
          资产编码 <code>AST-XXXXXXX</code> 由系统自动分配。初始状态为"活跃"，初始阶段为"发现"。
        </p>

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark
          initialValues={{
            asset_type: 'mab',
            current_phase: 'discovery',
            is_commercial: false,
          }}
          style={{ maxWidth: 880 }}
        >
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item
              label="内部名称"
              name="internal_name"
              rules={[{ required: true, message: '请填写内部名称' }]}
              style={{ flex: 2 }}
            >
              <Input maxLength={255} placeholder="例：CMAB-PD-1 Product" />
            </Form.Item>
            <Form.Item label="资产类型" name="asset_type" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={ASSET_TYPE_OPTIONS} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="商品名" name="trade_name" style={{ flex: 1 }}>
              <Input maxLength={255} placeholder="可选" />
            </Form.Item>
            <Form.Item label="INN 通用名" name="inn_name" style={{ flex: 1 }}>
              <Input maxLength={255} placeholder="可选" />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="当前阶段" name="current_phase" style={{ flex: 1 }}>
              <Select options={ASSET_PHASE_OPTIONS} />
            </Form.Item>
            <Form.Item label="治疗领域" name="therapeutic_area" style={{ flex: 1 }}>
              <Input maxLength={64} placeholder="例：肿瘤 / 自免" />
            </Form.Item>
          </Space>

          <Form.Item label="适应症" name="indication">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="剂型" name="dosage_form" style={{ flex: 1 }}>
              <Input maxLength={64} placeholder="例：注射剂 / 冻干粉" />
            </Form.Item>
            <Form.Item label="规格" name="strength" style={{ flex: 1 }}>
              <Input maxLength={64} placeholder="例：10 mg/mL × 10 mL" />
            </Form.Item>
            <Form.Item label="给药途径" name="route_of_administration" style={{ flex: 1 }}>
              <Input maxLength={32} placeholder="例：IV / SC / IM" />
            </Form.Item>
          </Space>

          <Form.Item name="is_commercial" valuePropName="checked">
            <Checkbox>已商业化资产</Checkbox>
          </Form.Item>

          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              创建资产
            </Button>
            <Button onClick={() => navigate('/assets')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
