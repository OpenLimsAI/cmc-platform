import {
  Breadcrumb,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Typography,
  message,
} from 'antd';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { equipmentsApi, type EquipmentCreatePayload } from '@/api/equipments';
import { EQUIPMENT_CATEGORY_OPTIONS } from '../constants';

const { Title, Text } = Typography;

export function EquipmentCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  // 支持从 LabOps "去 MDM 登记"跳转带入预填值(?code= / ?name=)
  const [searchParams] = useSearchParams();
  const prefill = {
    equipment_code: searchParams.get('code') ?? undefined,
    equipment_name: searchParams.get('name') ?? undefined,
  };

  const mutation = useMutation({
    mutationFn: (payload: EquipmentCreatePayload) => equipmentsApi.create(payload),
    onSuccess: (detail) => {
      message.success(`设备 ${detail.equipment_code} 创建成功`);
      navigate(`/equipments/${encodeURIComponent(detail.equipment_code)}`);
    },
  });

  const onFinish = async () => {
    const v = await form.validateFields();
    mutation.mutate({
      equipment_code: v.equipment_code || null,
      equipment_name: v.equipment_name,
      equipment_name_en: v.equipment_name_en,
      category: v.category,
      model: v.model,
      manufacturer: v.manufacturer,
      serial_no: v.serial_no,
      purchase_date: v.purchase_date?.format('YYYY-MM-DD') ?? null,
      asset_value: v.asset_value ?? null,
      supplier: v.supplier,
      description: v.description,
      notes: v.notes,
    });
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <Link to="/equipments">设备</Link> },
          { title: '新建' },
        ]}
      />
      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          新建设备
        </Title>
        <Text type="secondary">
          仅登记主数据（身份/采购属性）；位置、负责人、校验/维护/维修在 CMC LabOps Portal 维护
        </Text>
      </Card>

      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 880 }} initialValues={prefill}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="equipment_code"
                label="设备编码（留空自动生成 EQP-yyyyXXXXXX）"
                rules={[{ max: 32 }]}
              >
                <Input placeholder="可沿用历史编号，或留空自动生成" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="category"
                label="设备分类"
                rules={[{ required: true, message: '请选择设备分类' }]}
              >
                <Select options={EQUIPMENT_CATEGORY_OPTIONS} placeholder="分析仪器 / 实验设备 / 辅助设备" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="equipment_name"
                label="设备名称"
                rules={[{ required: true, message: '请输入设备名称' }, { max: 255 }]}
              >
                <Input placeholder="如 高效液相色谱仪" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="equipment_name_en" label="英文名称" rules={[{ max: 255 }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="model" label="型号规格" rules={[{ max: 200 }]}>
                <Input placeholder="如 LC-2030C 3D" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="manufacturer" label="生产商" rules={[{ max: 100 }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="serial_no" label="序列号" rules={[{ max: 100 }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="purchase_date" label="购入日期">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="asset_value" label="资产价值(元)">
                <InputNumber min={0} precision={2} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="supplier" label="供应商" rules={[{ max: 200 }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Space>
            <Button type="primary" loading={mutation.isPending} onClick={onFinish}>
              创建
            </Button>
            <Button onClick={() => navigate('/equipments')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
