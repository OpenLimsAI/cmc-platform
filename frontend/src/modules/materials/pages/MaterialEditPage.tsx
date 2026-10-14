import { useEditSnapshot } from '@/shared/hooks/useEditSnapshot';
import { useEffect, useState } from 'react';
import {
  AutoComplete,
  Breadcrumb,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  Result,
  Row,
  Select,
  Skeleton,
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
  CATEGORY_OPTIONS,
  GRADE_SUGGESTIONS,
  HAZARD_CLASS_OPTIONS,
  MATERIAL_STATUS_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
  PHYSICAL_FORM_SUGGESTIONS,
  SOURCE_TYPE_OPTIONS,
  STORAGE_CONDITION_SUGGESTIONS,
  UNIT_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

interface FormValues extends MaterialUpdatePayload {}

export function MaterialEditPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { capture, version } = useEditSnapshot(code);
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
    if (material && capture(material.version)) {
      form.resetFields();
      form.setFieldsValue({
        material_name: material.material_name,
        material_name_en: material.material_name_en ?? undefined,
        material_type: material.material_type,
        category: material.category ?? undefined,
        substance_code: material.substance_code ?? undefined,
        manufacturer: material.manufacturer ?? undefined,
        catalog_no: material.catalog_no ?? undefined,
        spec_model: material.spec_model ?? undefined,
        unit: material.unit,
        package_spec: material.package_spec ?? undefined,
        hazard_class: material.hazard_class ?? undefined,
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
  }, [material, form, capture]);

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
      version: version.current,
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

        <Form<FormValues> form={form} layout="vertical" onFinish={onFinish}>
          {/* ── 基本信息 ── */}
          <Divider orientation="left" orientationMargin={0} style={{ marginTop: 0 }}>
            <Text strong>基本信息</Text>
          </Divider>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item label="物料编码">
                <Input value={material.material_code} disabled />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="物料类型" name="material_type">
                <Select options={MATERIAL_TYPE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="物料分类" name="category">
                <Select options={CATEGORY_OPTIONS} allowClear showSearch />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item label="物料名称" name="material_name" rules={[{ required: true }]}>
                <Input maxLength={255} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item label="英文名" name="material_name_en">
                <Input maxLength={255} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item label="等级" name="grade">
                <AutoComplete
                  options={GRADE_SUGGESTIONS.map((v) => ({ value: v }))}
                  allowClear
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="默认计量单位" name="unit" rules={[{ required: true }]}>
                <Select options={UNIT_OPTIONS} showSearch />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="危化品分类" name="hazard_class">
                <Select mode="multiple" options={HAZARD_CLASS_OPTIONS} allowClear />
              </Form.Item>
            </Col>
          </Row>

          {/* ── 供应商与规格 ── */}
          <Divider orientation="left" orientationMargin={0}>
            <Text strong>供应商与规格</Text>
          </Divider>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item label="生产商" name="manufacturer">
                <Input maxLength={100} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="货号" name="catalog_no">
                <Input maxLength={100} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="包装规格" name="package_spec">
                <Input maxLength={100} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item label="规格型号" name="spec_model">
                <Input maxLength={200} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={6}>
              <Form.Item label="物理形态" name="physical_form">
                <AutoComplete options={PHYSICAL_FORM_SUGGESTIONS.map((v) => ({ value: v }))} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={6}>
              <Form.Item label="存储条件" name="storage_condition">
                <AutoComplete options={STORAGE_CONDITION_SUGGESTIONS.map((v) => ({ value: v }))} />
              </Form.Item>
            </Col>
          </Row>

          {/* ── 来源与关联 ── */}
          <Divider orientation="left" orientationMargin={0}>
            <Text strong>来源与关联</Text>
          </Divider>
          <Row gutter={16}>
            <Col xs={24} sm={6}>
              <Form.Item label="来源类型" name="source_type">
                <Select options={SOURCE_TYPE_OPTIONS} allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="来源名称" name="source_name">
                <Input maxLength={128} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={10}>
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
            </Col>
          </Row>

          {/* ── 状态与描述 ── */}
          <Divider orientation="left" orientationMargin={0}>
            <Text strong>状态与描述</Text>
          </Divider>
          <Row gutter={16}>
            <Col xs={24} sm={6}>
              <Form.Item label="状态" name="status" tooltip="物料状态无状态机，可直接更新">
                <Select options={MATERIAL_STATUS_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item label="描述" name="description">
                <Input.TextArea rows={3} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item label="备注" name="notes">
                <Input.TextArea rows={3} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item
                label="变更原因"
                name="change_reason"
                tooltip="将写入审计日志（21 CFR Part 11）。建议填写。"
              >
                <Input.TextArea rows={2} placeholder="说明此次变更的业务依据" />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ marginTop: 8 }}>
            <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
              保存
            </Button>
            <Button
              style={{ marginLeft: 12 }}
              onClick={() => navigate(`/materials/${encodeURIComponent(material.material_code)}`)}
            >
              取消
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  );
}
