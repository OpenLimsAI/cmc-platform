import { useEffect } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Result,
  Select,
  Skeleton,
  Space,
  Typography,
  message,
} from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { assetsApi } from '@/api/assets';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type { AssetUpdatePayload } from '@/api/types';
import { ASSET_PHASE_OPTIONS, ASSET_TYPE_OPTIONS } from '../constants';

const { Title } = Typography;

interface FormValues {
  internal_name?: string;
  trade_name?: string;
  inn_name?: string;
  asset_type?: AssetUpdatePayload['asset_type'];
  current_phase?: AssetUpdatePayload['current_phase'];
  therapeutic_area?: string;
  indication?: string;
  dosage_form?: string;
  strength?: string;
  route_of_administration?: string;
  is_commercial?: boolean;
  description?: string;
  notes?: string;
  change_reason?: string;
}

export function AssetEditPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();

  const {
    data: asset,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['asset', code],
    queryFn: () => assetsApi.get(code!),
    enabled: !!code,
  });

  useEffect(() => {
    if (asset) {
      form.setFieldsValue({
        internal_name: asset.internal_name,
        trade_name: asset.trade_name ?? undefined,
        inn_name: asset.inn_name ?? undefined,
        asset_type: asset.asset_type,
        current_phase: asset.current_phase,
        therapeutic_area: asset.therapeutic_area ?? undefined,
        indication: asset.indication ?? undefined,
        dosage_form: asset.dosage_form ?? undefined,
        strength: asset.strength ?? undefined,
        route_of_administration: asset.route_of_administration ?? undefined,
        is_commercial: asset.is_commercial,
        description: asset.description ?? undefined,
        notes: asset.notes ?? undefined,
      });
    }
  }, [asset, form]);

  const updateMutation = useMutation({
    mutationFn: (payload: AssetUpdatePayload) => assetsApi.update(code!, payload),
    onSuccess: (detail) => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['asset', code] });
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      navigate(`/assets/${encodeURIComponent(detail.asset_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      const status = err?.response?.status;
      if (status === 409) {
        message.error('数据已被他人修改，请刷新后重试');
      } else {
        message.error(err?.response?.data?.message ?? '更新失败');
      }
    },
  });

  const onFinish = (values: FormValues) => {
    if (!asset) return;
    updateMutation.mutate({ version: asset.version, ...values });
  };

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }
  if (isError || !asset) {
    return (
      <Result
        status="404"
        title="资产不存在"
        extra={
          <Button type="primary" onClick={() => navigate('/assets')}>
            返回列表
          </Button>
        }
      />
    );
  }

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/assets')}>资产</a> },
          {
            title: (
              <a onClick={() => navigate(`/assets/${encodeURIComponent(asset.asset_code)}`)}>
                {asset.asset_code}
              </a>
            ),
          },
          { title: '编辑' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          编辑资产 <code>{asset.asset_code}</code>{' '}
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            （当前版本 v{asset.version}）
          </Typography.Text>
        </Title>

        <Form<FormValues> form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 880 }}>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="内部名称" name="internal_name" style={{ flex: 2 }} rules={[{ required: true }]}>
              <Input maxLength={255} />
            </Form.Item>
            <Form.Item label="资产类型" name="asset_type" style={{ flex: 1 }}>
              <Select options={ASSET_TYPE_OPTIONS} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="商品名" name="trade_name" style={{ flex: 1 }}>
              <Input maxLength={255} />
            </Form.Item>
            <Form.Item label="INN 通用名" name="inn_name" style={{ flex: 1 }}>
              <Input maxLength={255} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item
              label="当前阶段"
              name="current_phase"
              tooltip="阶段变化会自动记录 phase_change_at，并写入 audit_log"
              style={{ flex: 1 }}
            >
              <Select options={ASSET_PHASE_OPTIONS} />
            </Form.Item>
            <Form.Item label="治疗领域" name="therapeutic_area" style={{ flex: 1 }}>
              <Input maxLength={64} />
            </Form.Item>
          </Space>

          <Form.Item label="适应症" name="indication">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="剂型" name="dosage_form" style={{ flex: 1 }}>
              <Input maxLength={64} />
            </Form.Item>
            <Form.Item label="规格" name="strength" style={{ flex: 1 }}>
              <Input maxLength={64} />
            </Form.Item>
            <Form.Item label="给药途径" name="route_of_administration" style={{ flex: 1 }}>
              <Input maxLength={32} />
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

          <Form.Item
            label="变更原因"
            name="change_reason"
            tooltip="将写入审计日志（21 CFR Part 11）。建议填写。"
          >
            <Input.TextArea rows={2} placeholder="说明此次变更的业务依据" />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
              保存
            </Button>
            <Button onClick={() => navigate(`/assets/${encodeURIComponent(asset.asset_code)}`)}>
              取消
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
