import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Typography, Tabs, Descriptions, Tag, Button, Space, Modal, Input, message, Spin,
} from "antd";
import { ArrowLeftOutlined, StopOutlined } from "@ant-design/icons";
import { useState } from "react";
import {
  getEquipment, deactivateEquipment, STATUS_LABEL,
} from "../../../api/equipment";
import { useAuthStore } from "../../../stores/authStore";
import CalibrationTab from "../tabs/CalibrationTab";
import MaintenanceTab from "../tabs/MaintenanceTab";
import RepairTab from "../tabs/RepairTab";
import WarrantyTab from "../tabs/WarrantyTab";
import AttachmentTab from "../tabs/AttachmentTab";

export default function EquipmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const equipmentId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasRole } = useAuthStore();
  const canEdit = hasRole("SYS_ADMIN") || hasRole("CMC_EQUIPMENT_ADMIN");

  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [reason, setReason] = useState("");

  const { data: eq, isLoading } = useQuery({
    queryKey: ["equipmentDetail", equipmentId],
    queryFn: () => getEquipment(equipmentId).then((r) => r.data),
    enabled: Number.isFinite(equipmentId),
  });

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateEquipment(equipmentId, reason || undefined),
    onSuccess: () => {
      message.success("设备已报废(历史数据保留)");
      setDeactivateOpen(false);
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: ["equipmentDetail", equipmentId] });
    },
    onError: (err: unknown) =>
      message.error(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "操作失败",
      ),
  });

  if (isLoading || !eq) {
    return <Spin style={{ display: "block", margin: "80px auto" }} />;
  }

  const statusTag = STATUS_LABEL[eq.status];

  return (
    <>
      <Space style={{ marginBottom: 8 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/equipment")}>
          返回列表
        </Button>
        {canEdit && eq.is_active && (
          <Button danger icon={<StopOutlined />} onClick={() => setDeactivateOpen(true)}>
            报废
          </Button>
        )}
      </Space>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {eq.equipment_code} — {eq.name}{" "}
        {statusTag && <Tag color={statusTag.color}>{statusTag.text}</Tag>}
        {!eq.is_active && <Tag color="red">已报废</Tag>}
      </Typography.Title>

      <Tabs
        items={[
          {
            key: "basic",
            label: "基本信息",
            children: (
              <Descriptions bordered size="small" column={2}>
                <Descriptions.Item label="设备编号">{eq.equipment_code}</Descriptions.Item>
                <Descriptions.Item label="设备名称">{eq.name}</Descriptions.Item>
                <Descriptions.Item label="设备分类">{eq.category}</Descriptions.Item>
                <Descriptions.Item label="型号规格">{eq.model ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="生产商">{eq.manufacturer ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="序列号">{eq.serial_no ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="所在房间">{eq.location_room ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="安装位置">{eq.location_detail ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="负责人">{eq.responsible_person ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  {statusTag ? <Tag color={statusTag.color}>{statusTag.text}</Tag> : eq.status}
                </Descriptions.Item>
                <Descriptions.Item label="购入日期">{eq.purchase_date ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="启用日期">{eq.commission_date ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="资产价值(元)">{eq.asset_value ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="主数据来源">
                  {eq.data_source === "mdm" ? (
                    <Tag color="geekblue">MDM(ID: {eq.mdm_equipment_id ?? "?"})</Tag>
                  ) : (
                    <Tag>本地(待在 MDM 补登)</Tag>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="创建">{eq.created_by ?? "-"} @ {eq.created_at}</Descriptions.Item>
                {!eq.is_active && (
                  <>
                    <Descriptions.Item label="报废时间">{eq.deactivated_at ?? "-"}</Descriptions.Item>
                    <Descriptions.Item label="报废原因">
                      {eq.deactivate_reason ?? "-"}(操作人: {eq.deactivated_by ?? "-"})
                    </Descriptions.Item>
                  </>
                )}
                <Descriptions.Item label="备注" span={2}>{eq.remark ?? "-"}</Descriptions.Item>
              </Descriptions>
            ),
          },
          {
            key: "calibration",
            label: "校验记录",
            children: <CalibrationTab equipmentId={equipmentId} canEdit={canEdit && eq.is_active} />,
          },
          {
            key: "maintenance",
            label: "维护记录",
            children: <MaintenanceTab equipmentId={equipmentId} canEdit={canEdit && eq.is_active} />,
          },
          {
            key: "repair",
            label: "维修记录",
            children: <RepairTab equipmentId={equipmentId} canEdit={canEdit && eq.is_active} />,
          },
          {
            key: "warranty",
            label: "保修信息",
            children: <WarrantyTab equipmentId={equipmentId} canEdit={canEdit && eq.is_active} />,
          },
          {
            key: "attachment",
            label: "附件",
            children: <AttachmentTab equipmentId={equipmentId} canEdit={canEdit && eq.is_active} />,
          },
        ]}
      />

      <Modal
        open={deactivateOpen}
        title={`报废设备: ${eq.equipment_code}`}
        onCancel={() => setDeactivateOpen(false)}
        onOk={() => deactivateMutation.mutate()}
        confirmLoading={deactivateMutation.isPending}
        okButtonProps={{ danger: true }}
        okText="确认报废"
      >
        <p>报废后设备从默认列表隐藏,历史校验/维护/维修数据完整保留。</p>
        <Input.TextArea
          rows={2}
          placeholder="报废原因(可选)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={200}
        />
      </Modal>
    </>
  );
}
