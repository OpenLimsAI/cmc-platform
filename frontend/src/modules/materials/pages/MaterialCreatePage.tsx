import { useState } from 'react';
import {
  AutoComplete,
  Breadcrumb,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  Row,
  Select,
  Typography,
  message,
} from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { materialsApi } from '@/api/materials';
import { applyFormErrors } from '@/shared/utils/formErrors';
import { searchApi } from '@/api/search';
import type { MaterialCreatePayload, MaterialType } from '@/api/types';
import {
  CATEGORY_OPTIONS,
  GRADE_SUGGESTIONS,
  HAZARD_CLASS_OPTIONS,
  MATERIAL_TYPE_OPTIONS,
  PHYSICAL_FORM_SUGGESTIONS,
  SOURCE_TYPE_OPTIONS,
  STORAGE_CONDITION_SUGGESTIONS,
  UNIT_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

interface FormValues extends MaterialCreatePayload {
  material_type: MaterialType;
}

export function MaterialCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  // 支持从 LabOps "去 MDM 登记"跳转带入预填值(?code= / ?name=)
  const [searchParams] = useSearchParams();
  const prefillCode = searchParams.get('code') ?? undefined;
  const prefillName = searchParams.get('name') ?? undefined;
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

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark
          initialValues={{
            material_type: 'reagent',
            unit: 'ea',
            material_code: prefillCode,
            material_name: prefillName,
          }}
        >
          {/* ── 基本信息 ── */}
          <Divider orientation="left" orientationMargin={0} style={{ marginTop: 0 }}>
            <Text strong>基本信息</Text>
          </Divider>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item
                label="物料编码"
                name="material_code"
                rules={[
                  { required: true, message: '请输入物料编码' },
                  { max: 20, message: '最多 20 个字符' },
                ]}
                tooltip="公司内部物料编码，创建后不可修改"
              >
                <Input maxLength={20} placeholder="例：R-00123" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item
                label="物料类型"
                name="material_type"
                rules={[{ required: true }]}
              >
                <Select options={MATERIAL_TYPE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="物料分类" name="category">
                <Select
                  options={CATEGORY_OPTIONS}
                  allowClear
                  showSearch
                  placeholder="选择物料分类"
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item
                label="物料名称"
                name="material_name"
                rules={[{ required: true, message: '请填写物料名称' }]}
              >
                <Input maxLength={255} placeholder="例：PBS 10× 缓冲液" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item label="英文名" name="material_name_en">
                <Input maxLength={255} placeholder="可选" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item label="等级" name="grade">
                <AutoComplete
                  options={GRADE_SUGGESTIONS.map((v) => ({ value: v }))}
                  placeholder="可输入或选择"
                  allowClear
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item
                label="默认计量单位"
                name="unit"
                rules={[{ required: true, message: '请选择计量单位' }]}
              >
                <Select options={UNIT_OPTIONS} showSearch />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="危化品分类" name="hazard_class">
                <Select
                  mode="multiple"
                  options={HAZARD_CLASS_OPTIONS}
                  allowClear
                  placeholder="如不涉及可留空"
                />
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
                <Input maxLength={100} placeholder="例：Thermo Fisher" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="货号" name="catalog_no">
                <Input maxLength={100} placeholder="例：70011-044" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="包装规格" name="package_spec">
                <Input maxLength={100} placeholder="例：500 mL/瓶" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item label="规格型号" name="spec_model">
                <Input maxLength={200} placeholder="例：4.6×250 mm, 5 μm" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={6}>
              <Form.Item label="物理形态" name="physical_form">
                <AutoComplete
                  options={PHYSICAL_FORM_SUGGESTIONS.map((v) => ({ value: v }))}
                  placeholder="例：liquid"
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={6}>
              <Form.Item label="存储条件" name="storage_condition">
                <AutoComplete
                  options={STORAGE_CONDITION_SUGGESTIONS.map((v) => ({ value: v }))}
                  placeholder="例：2-8°C"
                />
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
                <Select options={SOURCE_TYPE_OPTIONS} allowClear placeholder="未指定" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="来源名称" name="source_name">
                <Input maxLength={128} placeholder="例：Gibco" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={10}>
              <Form.Item
                label="关联物质"
                name="substance_code"
                extra="选择该物料对应的 substance 主数据"
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

          {/* ── 描述 ── */}
          <Divider orientation="left" orientationMargin={0}>
            <Text strong>描述</Text>
          </Divider>
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

          <div style={{ marginTop: 8 }}>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              创建物料
            </Button>
            <Button style={{ marginLeft: 12 }} onClick={() => navigate('/materials')}>
              取消
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  );
}
