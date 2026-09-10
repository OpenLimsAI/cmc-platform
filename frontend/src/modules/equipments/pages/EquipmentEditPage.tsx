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
  Spin,
  Typography,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { equipmentsApi, type EquipmentUpdatePayload } from '@/api/equipments';
import {
  EQUIPMENT_CATEGORY_OPTIONS,
  EQUIPMENT_STATUS_OPTIONS,
  IT_CATEGORY,
} from '../constants';
import { WorkstationFields } from '../components/WorkstationFields';
import { GovernanceFields } from '../components/GovernanceFields';

const { Title, Text } = Typography;

export function EquipmentEditPage() {
  const { code = '' } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const { data: eq, isLoading } = useQuery({
    queryKey: ['equipment', code],
    queryFn: () => equipmentsApi.get(code),
    enabled: !!code,
  });

  const mutation = useMutation({
    mutationFn: (payload: EquipmentUpdatePayload) => equipmentsApi.update(code, payload),
    onSuccess: () => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['equipment', code] });
      queryClient.invalidateQueries({ queryKey: ['equipments'] });
      navigate(`/equipments/${encodeURIComponent(code)}`);
    },
  });

  if (isLoading || !eq) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }

  const onFinish = async () => {
    const v = await form.validateFields();
    mutation.mutate({
      equipment_no: v.equipment_no,
      fixed_asset_no: v.fixed_asset_no,
      equipment_name: v.equipment_name,
      equipment_name_en: v.equipment_name_en,
      category: v.category,
      model: v.model,
      manufacturer: v.manufacturer,
      serial_no: v.serial_no,
      rated_power: v.rated_power,
      origin: v.origin,
      purchase_date: v.purchase_date?.format('YYYY-MM-DD') ?? null,
      asset_value: v.asset_value ?? null,
      supplier: v.supplier,
      department: v.department,
      site: v.site,
      room: v.room,
      criticality: v.criticality ?? null,
      criticality_basis: v.criticality_basis,
      commission_date: v.commission_date?.format('YYYY-MM-DD') ?? null,
      status: v.status,
      has_workstation: !!v.has_workstation,
      workstation_info:
        v.category === IT_CATEGORY || !!v.has_workstation
          ? (v.workstation_info ?? null)
          : null,
      description: v.description,
      notes: v.notes,
      change_reason: v.change_reason,
    });
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <Link to="/equipments">设备</Link> },
          { title: <Link to={`/equipments/${encodeURIComponent(code)}`}>{code}</Link> },
          { title: '编辑' },
        ]}
      />
      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          编辑设备 · 设备ID: {eq.equipment_code}
        </Title>
        <Text type="secondary">设备ID（系统生成）不可修改；设备编号/固资编号可维护</Text>
      </Card>

      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 880 }}
          initialValues={{
            ...eq,
            purchase_date: eq.purchase_date ? dayjs(eq.purchase_date) : null,
            commission_date: eq.commission_date ? dayjs(eq.commission_date) : null,
            asset_value: eq.asset_value != null ? Number(eq.asset_value) : null,
            workstation_info: eq.workstation_info ?? {},
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="equipment_name"
                label="设备名称（中文）"
                rules={[{ required: true }, { max: 255 }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="equipment_name_en" label="设备名称（英文）" rules={[{ max: 255 }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="equipment_no" label="设备编号（业务/历史号）" rules={[{ max: 64 }]}>
                <Input placeholder="如 QC001、11J1815002" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="fixed_asset_no" label="固资编号" rules={[{ max: 64 }]}>
                <Input placeholder="财务固定资产编号" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="设备分类" rules={[{ required: true }]}>
                <Select
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
            <Col span={12}>
              <Form.Item name="status" label="主数据状态">
                <Select options={EQUIPMENT_STATUS_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="model" label="型号规格" rules={[{ max: 200 }]}>
                <Input />
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
          <GovernanceFields />
          <WorkstationFields />

          <Form.Item name="description" label="主要性能参数描述">
            <Input.TextArea rows={2} placeholder="如 检测器类型、波长范围、流速范围、量程、精度等" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="change_reason" label="变更原因">
            <Input placeholder="本次修改的原因（写入审计）" maxLength={2000} />
          </Form.Item>

          <Space>
            <Button type="primary" loading={mutation.isPending} onClick={onFinish}>
              保存
            </Button>
            <Button onClick={() => navigate(`/equipments/${encodeURIComponent(code)}`)}>
              取消
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
