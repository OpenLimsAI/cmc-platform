import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Input,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { equipmentsApi } from '@/api/equipments';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import {
  EQUIPMENT_CATEGORY_OPTIONS,
  EQUIPMENT_STATUS_OPTIONS,
} from '../constants';

const { Title, Text } = Typography;

export function EquipmentDetailPage() {
  const { code = '' } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [reason, setReason] = useState('');

  const { data: eq, isLoading } = useQuery({
    queryKey: ['equipment', code],
    queryFn: () => equipmentsApi.get(code),
    enabled: !!code,
  });

  const deleteMutation = useMutation({
    mutationFn: () => equipmentsApi.delete(code, reason),
    onSuccess: () => {
      message.success('设备已删除（软删除，审计可追溯）');
      queryClient.invalidateQueries({ queryKey: ['equipments'] });
      navigate('/equipments');
    },
  });

  if (isLoading || !eq) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }

  const categoryDef = EQUIPMENT_CATEGORY_OPTIONS.find((o) => o.value === eq.category);
  const statusDef = EQUIPMENT_STATUS_OPTIONS.find((o) => o.value === eq.status);

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <Link to="/equipments">设备</Link> },
          { title: eq.equipment_code },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {eq.equipment_code} — {eq.equipment_name}{' '}
              <Tag color={categoryDef?.color}>{eq.category}</Tag>
              <Tag color={statusDef?.color}>{statusDef?.label ?? eq.status}</Tag>
            </Title>
            <Text type="secondary">
              主数据（身份/采购属性）；日常运营（位置/负责人/校验/维护/维修）在 CMC LabOps Portal
            </Text>
          </div>
          <Space>
            <PermissionGuard permission="equipment:update">
              <Button
                icon={<EditOutlined />}
                onClick={() => navigate(`/equipments/${encodeURIComponent(code)}/edit`)}
              >
                编辑
              </Button>
              <Button danger icon={<DeleteOutlined />} onClick={() => setDeleteOpen(true)}>
                删除
              </Button>
            </PermissionGuard>
          </Space>
        </div>
      </Card>

      <Card>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="设备编码">{eq.equipment_code}</Descriptions.Item>
          <Descriptions.Item label="设备名称">{eq.equipment_name}</Descriptions.Item>
          <Descriptions.Item label="英文名称">{eq.equipment_name_en ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="设备分类">{eq.category}</Descriptions.Item>
          <Descriptions.Item label="型号规格">{eq.model ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="生产商">{eq.manufacturer ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="序列号">{eq.serial_no ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="供应商">{eq.supplier ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="购入日期">{eq.purchase_date ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="资产价值(元)">{eq.asset_value ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            <TimeDisplay value={eq.created_at} />
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            <TimeDisplay value={eq.updated_at} />
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {eq.description ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="备注" span={2}>
            {eq.notes ?? '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Modal
        open={deleteOpen}
        title={`删除设备: ${eq.equipment_code}`}
        onCancel={() => setDeleteOpen(false)}
        onOk={() => {
          if (reason.trim().length < 5) {
            message.warning('请填写删除原因（至少 5 个字符）');
            return;
          }
          deleteMutation.mutate();
        }}
        confirmLoading={deleteMutation.isPending}
        okButtonProps={{ danger: true }}
        okText="确认删除"
      >
        <p>软删除：记录保留并可审计追溯。下游 LabOps 的运营数据不受影响。</p>
        <Input.TextArea
          rows={2}
          placeholder="删除原因（必填，≥5 字符）"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={2000}
        />
      </Modal>
    </div>
  );
}
