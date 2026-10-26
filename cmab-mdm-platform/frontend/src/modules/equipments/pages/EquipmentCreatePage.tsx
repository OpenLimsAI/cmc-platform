import { useIdempotentCreate } from '@/shared/hooks/useIdempotentCreate';
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
import { EQUIPMENT_CATEGORY_OPTIONS, IT_CATEGORY } from '../constants';
import { WorkstationFields } from '../components/WorkstationFields';
import { GovernanceFields } from '../components/GovernanceFields';

const { Title, Text } = Typography;

export function EquipmentCreatePage() {
  const createOnce = useIdempotentCreate((payload: EquipmentCreatePayload, key: string) => equipmentsApi.create(payload, key));
  const navigate = useNavigate();
  const [form] = Form.useForm();
  // 支持从 LabOps "去 MDM 登记"跳转带入预填值(?code= / ?name=)
  const [searchParams] = useSearchParams();
  const prefill = {
    // 设备ID 系统生成；LabOps 跳转带来的 ?code= 是业务/历史号，预填到设备编号
    equipment_no: searchParams.get('code') ?? undefined,
    equipment_name: searchParams.get('name') ?? undefined,
  };

  const mutation = useMutation({
    mutationFn: createOnce,
    onSuccess: (detail) => {
      message.success(`设备 ${detail.equipment_code} 创建成功`);
      navigate(`/equipments/${encodeURIComponent(detail.equipment_code)}`);
    },

    onError: (err: any) => message.error(err?.response?.data?.message ?? err?.message ?? '创建失败'),
  });

  const onFinish = async () => {
    const v = await form.validateFields();
    const showWs = v.category === IT_CATEGORY || !!v.has_workstation;
    mutation.mutate({
      equipment_no: v.equipment_no,
      fixed_asset_no: v.fixed_asset_no,
      equipment_name: v.equipment_name,
      equipment_name_en: v.equipment_name_en,
      alias: v.alias,
      category: v.category,
      model: v.model,
      manufacturer: v.manufacturer,
      serial_no: v.serial_no,
      rated_power: v.rated_power,
      total_weight: v.total_weight,
      origin: v.origin,
      manufacture_date: v.manufacture_date?.format('YYYY-MM-DD') ?? null,
      asset_value: v.asset_value ?? null,
      supplier: v.supplier,
      department: v.department,
      site: v.site,
      room: v.room,
      criticality: v.criticality ?? null,
      criticality_basis: v.criticality_basis,
      commission_date: v.commission_date?.format('YYYY-MM-DD') ?? null,
      has_workstation: !!v.has_workstation,
      workstation_info: showWs ? (v.workstation_info ?? null) : null,
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
          全公司设备清单（设备部维护）：身份、采购属性、使用部门/位置/分级；校准由计量专员、验证由验证部平台管理
        </Text>
      </Card>

      <Card>
        <Form form={form} layout="vertical" style={{ maxWidth: 880 }} initialValues={prefill}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            设备ID 由系统自动生成（EQP-yyyy-NNNNNN，全局唯一、不可改）；下方"设备编号"填业务/历史号
          </Text>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="equipment_no" label="设备编号（业务/历史号）" rules={[{ max: 64 }]}>
                <Input placeholder="如 QC001、11J1815002" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="fixed_asset_no" label="固资编号" rules={[{ max: 64 }]}>
                <Input placeholder="财务固定资产编号" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="category"
                label="设备分类"
                rules={[{ required: true, message: '请选择设备分类' }]}
              >
                <Select
                  placeholder="选择设备类型"
                  options={EQUIPMENT_CATEGORY_OPTIONS}
                  optionRender={(opt) => {
                    const o = EQUIPMENT_CATEGORY_OPTIONS.find((x) => x.value === opt.value);
                    return (
                      <div>
                        <div>{o?.label}</div>
                        <div style={{ fontSize: 12, color: '#999', whiteSpace: 'normal' }}>
                          {o?.hint}
                        </div>
                      </div>
                    );
                  }}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="equipment_name"
                label="设备名称（中文）"
                rules={[{ required: true, message: '请输入设备名称' }, { max: 255 }]}
              >
                <Input placeholder="如 高效液相色谱仪" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="equipment_name_en" label="设备名称（英文）" rules={[{ max: 255 }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="alias"
                label="别名/曾用名"
                tooltip="老员工习惯的旧称，多个用 ; 分隔（如 BR1-1;生物反应器系统1;发酵线1）。列表搜索会一并匹配。"
                rules={[{ max: 255 }]}
              >
                <Input placeholder="BR1-1;生物反应器系统1;发酵线1" />
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
              <Form.Item name="rated_power" label="额定功率" rules={[{ max: 64 }]}>
                <Input placeholder="如 1500W、220V/50Hz/2kW" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="origin" label="产地" rules={[{ max: 100 }]}>
                <Input placeholder="如 美国、德国、中国" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="total_weight" label="总重">
                <InputNumber min={0} precision={3} addonAfter="kg" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="manufacture_date" label="出厂日期">
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
          <GovernanceFields />
          <WorkstationFields />

          <Form.Item name="description" label="主要性能参数描述">
            <Input.TextArea rows={2} placeholder="如 检测器类型、波长范围、流速范围、量程、精度等" />
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
