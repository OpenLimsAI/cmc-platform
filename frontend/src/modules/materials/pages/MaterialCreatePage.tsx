import {
  AutoComplete,
  Breadcrumb,
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Typography,
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { materialsApi } from '@/api/materials';
import { applyFormErrors } from '@/shared/utils/formErrors';
import { searchApi } from '@/api/search';
import { useState } from 'react';
import type { MaterialCreatePayload, MaterialType } from '@/api/types';
import {
  MATERIAL_GRADE_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
  PHYSICAL_FORM_SUGGESTIONS,
  SOURCE_TYPE_OPTIONS,
  STORAGE_CONDITION_SUGGESTIONS,
} from '../constants';

const { Title } = Typography;

interface FormValues extends MaterialCreatePayload {
  material_type: MaterialType;
}

export function MaterialCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [subQuery, setSubQuery] = useState('');

  const { data: subSearchData } = useQuery({
    queryKey: ['material-create-sub-search', subQuery],
    queryFn: () => searchApi.search(subQuery, ['substance'], 10),
    enabled: subQuery.length >= 1,
    staleTime: 5_000,
  });

  const subOptions =
    subSearchData?.results.substance.items.map((h) => ({
      value: h.code,
      label: `${h.code} · ${h.name}`,
    })) ?? [];

  const createMutation = useMutation({
    mutationFn: (payload: MaterialCreatePayload) => materialsApi.create(payload),
    onSuccess: (detail) => {
      message.success(`物料已创建：${detail.material_code}`);
      navigate(`/materials/${encodeURIComponent(detail.material_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      message.error(err?.response?.data?.message ?? '创建失败');
    },
  });

  const onFinish = (values: FormValues) => {
    createMutation.mutate({
      ...values,
      // 空 substance_code 不要传
      substance_code: values.substance_code || undefined,
    } as MaterialCreatePayload);
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/materials')}>物料</a> },
          { title: '新建物料' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          新建物料
        </Title>
        <p style={{ color: '#8c8c8c', marginTop: -8 }}>
          物料编码 <code>MAT-yyyy-XXXXXX</code> 由系统按年自动分配。初始状态为"在用"。
        </p>

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark
          initialValues={{ material_type: 'candidate' }}
          style={{ maxWidth: 880 }}
        >
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item
              label="物料名称"
              name="material_name"
              rules={[{ required: true, message: '请填写物料名称' }]}
              style={{ flex: 2 }}
            >
              <Input maxLength={255} placeholder="例：CMAB-101 Engineering Run #1" />
            </Form.Item>
            <Form.Item
              label="物料类型"
              name="material_type"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select options={MATERIAL_TYPE_OPTIONS} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="英文名" name="material_name_en" style={{ flex: 1 }}>
              <Input maxLength={255} placeholder="可选" />
            </Form.Item>
            <Form.Item label="等级" name="grade" style={{ flex: 1 }}>
              <Select
                options={MATERIAL_GRADE_OPTIONS}
                allowClear
                placeholder="未指定"
              />
            </Form.Item>
          </Space>

          <Form.Item
            label="关联物质（可选）"
            name="substance_code"
            extra="选择该物料对应的 substance 主数据；obsoleted 状态的物质不允许绑定"
          >
            <AutoComplete
              options={subOptions}
              onSearch={setSubQuery}
              placeholder="输入 SUB- 编码或物质名称搜索"
              allowClear
            />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="物理形态" name="physical_form" style={{ flex: 1 }}>
              <AutoComplete
                options={PHYSICAL_FORM_SUGGESTIONS.map((v) => ({ value: v }))}
                placeholder="例：liquid / lyophilized"
              />
            </Form.Item>
            <Form.Item label="存储条件" name="storage_condition" style={{ flex: 1 }}>
              <AutoComplete
                options={STORAGE_CONDITION_SUGGESTIONS.map((v) => ({ value: v }))}
                placeholder="例：2-8°C"
              />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="来源类型" name="source_type" style={{ flex: 1 }}>
              <Select options={SOURCE_TYPE_OPTIONS} allowClear placeholder="未指定" />
            </Form.Item>
            <Form.Item label="来源名称" name="source_name" style={{ flex: 2 }}>
              <Input maxLength={128} placeholder="例：Pilot Plant 北区 / 某 CDMO" />
            </Form.Item>
          </Space>

          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              创建物料
            </Button>
            <Button onClick={() => navigate('/materials')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
