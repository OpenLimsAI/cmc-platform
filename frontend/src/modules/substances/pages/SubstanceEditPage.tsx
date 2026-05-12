import { useEffect, useMemo } from 'react';
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Radio,
  Result,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { substancesApi } from '@/api/substances';
import type {
  Confidentiality,
  ProteinExtensionInput,
  SubstanceUpdatePayload,
} from '@/api/types';
import { SubstanceTypeTag } from '@/shared/components/SubstanceTypeTag';
import {
  EXPRESSION_SYSTEM_OPTIONS,
  ISOTYPE_OPTIONS,
  PROTEIN_TYPES,
  cleanedSequenceLength,
} from '../constants';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface FormShape {
  internal_code?: string;
  preferred_name: string;
  preferred_name_en?: string;
  target?: string;
  target_type?: string;
  modality?: string;
  is_proprietary: boolean;
  confidentiality: Confidentiality;
  description?: string;
  notes?: string;
  protein?: ProteinExtensionInput;
  change_reason?: string;
}

export function SubstanceEditPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormShape>();

  const { data: sub, isLoading, isError } = useQuery({
    queryKey: ['substance', code],
    queryFn: () => substancesApi.get(code!, 'protein,xrefs'),
    enabled: !!code,
  });

  const needsProtein = useMemo(
    () => (sub ? PROTEIN_TYPES.includes(sub.substance_type) : false),
    [sub]
  );

  // 初始值预填
  useEffect(() => {
    if (!sub) return;
    form.setFieldsValue({
      internal_code: sub.internal_code ?? undefined,
      preferred_name: sub.preferred_name,
      preferred_name_en: sub.preferred_name_en ?? undefined,
      target: sub.target ?? undefined,
      target_type: sub.target_type ?? undefined,
      modality: sub.modality ?? undefined,
      is_proprietary: sub.is_proprietary,
      confidentiality: sub.confidentiality,
      description: sub.description ?? undefined,
      notes: sub.notes ?? undefined,
      protein: sub.protein
        ? {
            isotype: sub.protein.isotype ?? undefined,
            architecture: sub.protein.architecture ?? undefined,
            expression_system: sub.protein.expression_system ?? undefined,
            cell_line: sub.protein.cell_line ?? undefined,
            molecular_weight_da: sub.protein.molecular_weight_da ?? undefined,
            heavy_chain_sequence: sub.protein.heavy_chain_sequence ?? undefined,
            light_chain_sequence: sub.protein.light_chain_sequence ?? undefined,
          }
        : undefined,
    });
  }, [sub, form]);

  const hcSeq = Form.useWatch(['protein', 'heavy_chain_sequence'], form);
  const lcSeq = Form.useWatch(['protein', 'light_chain_sequence'], form);

  const mutation = useMutation({
    mutationFn: (payload: SubstanceUpdatePayload) => substancesApi.update(code!, payload),
    onSuccess: (data) => {
      message.success(`已更新 (version → ${data.version})`);
      queryClient.invalidateQueries({ queryKey: ['substance', code] });
      queryClient.invalidateQueries({ queryKey: ['substances'] });
      navigate(`/substances/${data.substance_code}`);
    },
  });

  if (isLoading || !sub) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    );
  }
  if (isError) {
    return (
      <Result
        status="404"
        title="未找到该物质"
        extra={<Button onClick={() => navigate('/substances')}>返回列表</Button>}
      />
    );
  }

  const handleSubmit = async () => {
    const v = await form.validateFields();

    const payload: SubstanceUpdatePayload = {
      version: sub.version,
      change_reason: v.change_reason?.trim() || undefined,
      internal_code: v.internal_code?.trim() || undefined,
      preferred_name: v.preferred_name.trim(),
      preferred_name_en: v.preferred_name_en?.trim() || undefined,
      target: v.target?.trim() || undefined,
      target_type: v.target_type?.trim() || undefined,
      modality: v.modality?.trim() || undefined,
      is_proprietary: v.is_proprietary,
      confidentiality: v.confidentiality,
      description: v.description?.trim() || undefined,
      notes: v.notes?.trim() || undefined,
    };

    if (needsProtein && v.protein) {
      const p = v.protein;
      const proteinPayload: ProteinExtensionInput = {
        isotype: p.isotype || undefined,
        architecture: p.architecture || undefined,
        expression_system: p.expression_system || undefined,
        cell_line: p.cell_line || undefined,
        molecular_weight_da: p.molecular_weight_da ?? undefined,
        heavy_chain_sequence: p.heavy_chain_sequence?.trim() || undefined,
        light_chain_sequence: p.light_chain_sequence?.trim() || undefined,
      };
      if (Object.values(proteinPayload).some((x) => x !== undefined && x !== '')) {
        payload.protein = proteinPayload;
      }
    }

    mutation.mutate(payload);
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/substances')}>物质</a> },
          {
            title: (
              <a onClick={() => navigate(`/substances/${sub.substance_code}`)}>
                {sub.substance_code} - {sub.preferred_name}
              </a>
            ),
          },
          { title: '编辑' },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              编辑物质
            </Title>
            <Space style={{ marginTop: 8 }} size="middle">
              <Text strong>{sub.substance_code}</Text>
              <SubstanceTypeTag type={sub.substance_type} />
              <Tag>当前 version: {sub.version}</Tag>
              <Text type="secondary">类型不可修改</Text>
            </Space>
          </div>
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="编辑会生成审计记录（21 CFR Part 11）。建议填写变更原因，便于事后追溯。"
      />

      <Form<FormShape> form={form} layout="vertical" autoComplete="off">
        <Card title="基本信息" style={{ marginBottom: 16 }}>
          <Form.Item
            name="internal_code"
            label="内部代号"
            tooltip="留空表示不修改/不设置"
            rules={[{ max: 64 }]}
          >
            <Input placeholder="如：CMAB-203" />
          </Form.Item>

          <Form.Item
            name="preferred_name"
            label="首选名称（中文/通用）"
            rules={[{ required: true, message: '必填' }, { max: 255 }]}
          >
            <Input />
          </Form.Item>

          <Form.Item name="preferred_name_en" label="首选名称（英文）" rules={[{ max: 255 }]}>
            <Input />
          </Form.Item>

          <Space size="large" style={{ display: 'flex', width: '100%' }}>
            <Form.Item name="target" label="靶点" style={{ flex: 1 }} rules={[{ max: 128 }]}>
              <Input />
            </Form.Item>
            <Form.Item name="target_type" label="靶点类型" style={{ flex: 1 }} rules={[{ max: 64 }]}>
              <Input />
            </Form.Item>
            <Form.Item name="modality" label="模态描述" style={{ flex: 1 }} rules={[{ max: 64 }]}>
              <Input />
            </Form.Item>
          </Space>

          <Space size="large">
            <Form.Item name="confidentiality" label="保密等级" rules={[{ required: true }]}>
              <Radio.Group>
                <Radio value="public">公开</Radio>
                <Radio value="internal">内部</Radio>
                <Radio value="restricted">受限</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item name="is_proprietary" label="是否专有" valuePropName="checked">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          </Space>

          <Form.Item name="description" label="描述">
            <TextArea rows={2} maxLength={2000} showCount />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <TextArea rows={2} maxLength={2000} showCount />
          </Form.Item>
        </Card>

        {needsProtein && (
          <Card title="蛋白属性" style={{ marginBottom: 16 }}>
            <Space size="large" style={{ display: 'flex', width: '100%' }}>
              <Form.Item name={['protein', 'isotype']} label="同型 (Isotype)" style={{ flex: 1 }}>
                <Select
                  allowClear
                  showSearch
                  options={ISOTYPE_OPTIONS.map((v) => ({ value: v, label: v }))}
                />
              </Form.Item>
              <Form.Item name={['protein', 'architecture']} label="架构" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
            </Space>

            <Space size="large" style={{ display: 'flex', width: '100%' }}>
              <Form.Item name={['protein', 'expression_system']} label="表达系统" style={{ flex: 1 }}>
                <Select
                  allowClear
                  showSearch
                  options={EXPRESSION_SYSTEM_OPTIONS.map((v) => ({ value: v, label: v }))}
                />
              </Form.Item>
              <Form.Item name={['protein', 'cell_line']} label="细胞株" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
              <Form.Item
                name={['protein', 'molecular_weight_da']}
                label="分子量 (Da)"
                style={{ flex: 1 }}
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
            </Space>

            <Form.Item
              name={['protein', 'heavy_chain_sequence']}
              label={
                <span>
                  重链序列{' '}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    （当前 {cleanedSequenceLength(hcSeq)} aa）
                  </Text>
                </span>
              }
            >
              <TextArea rows={4} style={{ fontFamily: 'Consolas, monospace', fontSize: 13 }} />
            </Form.Item>
            <Form.Item
              name={['protein', 'light_chain_sequence']}
              label={
                <span>
                  轻链序列{' '}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    （当前 {cleanedSequenceLength(lcSeq)} aa）
                  </Text>
                </span>
              }
            >
              <TextArea rows={4} style={{ fontFamily: 'Consolas, monospace', fontSize: 13 }} />
            </Form.Item>
          </Card>
        )}

        <Card title="变更原因（推荐填写）" style={{ marginBottom: 16 }}>
          <Form.Item
            name="change_reason"
            label="本次修改原因"
            tooltip="将记入审计日志的 reason 字段，事后可在审计 Tab 查询"
            rules={[{ max: 2000 }]}
          >
            <TextArea rows={2} placeholder="例如：补充蛋白序列信息" />
          </Form.Item>
        </Card>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <Button onClick={() => navigate(`/substances/${sub.substance_code}`)}>取消</Button>
          <Button type="primary" loading={mutation.isPending} onClick={handleSubmit}>
            保存修改
          </Button>
        </div>
      </Form>
    </div>
  );
}
