import { useEffect, useState } from 'react';
import {
  AutoComplete,
  Breadcrumb,
  Button,
  Card,
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
import { materialsApi } from '@/api/materials';
import { applyFormErrors } from '@/shared/utils/formErrors';
import { searchApi } from '@/api/search';
import type { MaterialUpdatePayload } from '@/api/types';
import {
  MATERIAL_GRADE_OPTIONS,
  MATERIAL_STATUS_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
  PHYSICAL_FORM_SUGGESTIONS,
  SOURCE_TYPE_OPTIONS,
  STORAGE_CONDITION_SUGGESTIONS,
} from '../constants';

const { Title } = Typography;

interface FormValues extends MaterialUpdatePayload {}

export function MaterialEditPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [subQuery, setSubQuery] = useState('');

  const { data: material, isLoading, isError } = useQuery({
    queryKey: ['material', code],
    queryFn: () => materialsApi.get(code!),
    enabled: !!code,
  });

  const { data: subSearchData } = useQuery({
    queryKey: ['material-edit-sub-search', subQuery],
    queryFn: () => searchApi.search(subQuery, ['substance'], 10),
    enabled: subQuery.length >= 1,
    staleTime: 5_000,
  });

  const subOptions =
    subSearchData?.results.substance.items.map((h) => ({
      value: h.code,
      label: `${h.code} · ${h.name}`,
    })) ?? [];

  useEffect(() => {
    if (material) {
      form.setFieldsValue({
        material_name: material.material_name,
        material_name_en: material.material_name_en ?? undefined,
        material_type: material.material_type,
        substance_code: material.substance_code ?? undefined,
        physical_form: material.physical_form ?? undefined,
        storage_condition: material.storage_condition ?? undefined,
        source_type: material.source_type ?? undefined,
        source_name: material.source_name ?? undefined,
        grade: material.grade ?? undefined,
        status: material.status,
        description: material.description ?? undefined,
        notes: material.notes ?? undefined,
      });
    }
  }, [material, form]);

  const updateMutation = useMutation({
    mutationFn: (payload: MaterialUpdatePayload) => materialsApi.update(code!, payload),
    onSuccess: (detail) => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['material', code] });
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      navigate(`/materials/${encodeURIComponent(detail.material_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      message.error(err?.response?.data?.message ?? '更新失败');
    },
  });

  const onFinish = (values: FormValues) => {
    updateMutation.mutate({
      ...values,
      // 用空字符串区分"未改"与"清空" — 这里若用户清空就传 null
      substance_code: values.substance_code === '' ? null : values.substance_code,
    });
  };

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }
  if (isError || !material) {
    return (
      <Result
        status="404"
        title="物料不存在"
        extra={
          <Button type="primary" onClick={() => navigate('/materials')}>
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
          { title: <a onClick={() => navigate('/materials')}>物料</a> },
          {
            title: (
              <a onClick={() => navigate(`/materials/${encodeURIComponent(material.material_code)}`)}>
                {material.material_code}
              </a>
            ),
          },
          { title: '编辑' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          编辑物料 <code>{material.material_code}</code>
        </Title>

        <Form<FormValues> form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 880 }}>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="物料名称" name="material_name" style={{ flex: 2 }} rules={[{ required: true }]}>
              <Input maxLength={255} />
            </Form.Item>
            <Form.Item label="物料类型" name="material_type" style={{ flex: 1 }}>
              <Select options={MATERIAL_TYPE_OPTIONS} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="英文名" name="material_name_en" style={{ flex: 1 }}>
              <Input maxLength={255} />
            </Form.Item>
            <Form.Item label="等级" name="grade" style={{ flex: 1 }}>
              <Select options={MATERIAL_GRADE_OPTIONS} allowClear />
            </Form.Item>
          </Space>

          <Form.Item
            label="关联物质"
            name="substance_code"
            extra="留空表示解除关联；obsoleted 状态的物质不允许绑定"
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
              <AutoComplete options={PHYSICAL_FORM_SUGGESTIONS.map((v) => ({ value: v }))} />
            </Form.Item>
            <Form.Item label="存储条件" name="storage_condition" style={{ flex: 1 }}>
              <AutoComplete options={STORAGE_CONDITION_SUGGESTIONS.map((v) => ({ value: v }))} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="来源类型" name="source_type" style={{ flex: 1 }}>
              <Select options={SOURCE_TYPE_OPTIONS} allowClear />
            </Form.Item>
            <Form.Item label="来源名称" name="source_name" style={{ flex: 2 }}>
              <Input maxLength={128} />
            </Form.Item>
          </Space>

          <Form.Item
            label="状态"
            name="status"
            tooltip="物料状态无状态机，可直接 PUT 更新（§10.1）"
          >
            <Select options={MATERIAL_STATUS_OPTIONS} />
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
            <Button onClick={() => navigate(`/materials/${encodeURIComponent(material.material_code)}`)}>
              取消
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
