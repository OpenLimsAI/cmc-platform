import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Typography, Card, Row, Col, Statistic, Button, List, Tag, Space, Spin,
} from "antd";
import {
  ImportOutlined, ExportOutlined, PlusOutlined, SafetyCertificateOutlined,
  RightOutlined, AlertOutlined,
} from "@ant-design/icons";
import { getDashboardStats } from "../../../api/dashboard";
import { expiryAlerts, lowStockAlerts } from "../../../api/inventory";
import { equipmentAlerts, type EquipmentAlert } from "../../../api/equipment";
import { useAuthStore } from "../../../stores/authStore";

interface ExpiryAlertRow {
  batch_id: number;
  material_code: string;
  name_cn: string;
  batch_no: string;
  expiry_date: string;
  days_to_expiry: number;
  severity: string; // EXPIRED | URGENT | WARNING
}

interface LowStockRow {
  material_id: number;
  material_code: string;
  name_cn: string;
  unit: string;
  safety_stock: number;
  total_qty: number;
  gap: number;
}

const EQP_ALERT_TYPE: Record<string, string> = {
  calibration: "校验",
  maintenance: "维护",
  warranty: "保修",
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

/**
 * 仪表盘 (UI-LABOPS-001 §4.2 / FR-EQP-063):
 * 关键统计 + 待处理告警汇总 + 快捷入口 + 物料/设备预警概览。
 * 预警数据复用预警中心同款 API,这里只取摘要,明细去 /alerts。
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, canWrite, hasRole } = useAuthStore();
  const canEquip = hasRole("SYS_ADMIN") || hasRole("CMC_EQUIPMENT_ADMIN");

  const { data: stats } = useQuery({
    queryKey: ["dashboardStats"],
    queryFn: () => getDashboardStats().then((r) => r.data),
  });

  const { data: expiry = [], isLoading: expiryLoading } = useQuery({
    queryKey: ["expiryAlerts"],
    queryFn: () => expiryAlerts(90).then((r) => r.data as ExpiryAlertRow[]),
  });

  const { data: lowStock = [], isLoading: lowLoading } = useQuery({
    queryKey: ["lowStockAlerts"],
    queryFn: () => lowStockAlerts().then((r) => r.data as LowStockRow[]),
  });

  const { data: eqpAlerts = [], isLoading: eqpLoading } = useQuery({
    queryKey: ["equipmentAlerts"],
    queryFn: () => equipmentAlerts(30).then((r) => r.data),
  });

  // —— 告警汇总计数 ——
  const expired = expiry.filter((a) => a.severity === "EXPIRED").length;
  const nearExpiry = expiry.length - expired;
  const eqpRed = eqpAlerts.filter((a) => a.severity === "red").length;
  const eqpYellow = eqpAlerts.length - eqpRed;

  // —— 概览列表(各取前 5 条) ——
  const materialPreview: { key: string; color: string; text: string }[] = [
    ...expiry.slice(0, 5).map((a) => ({
      key: `e${a.batch_id}`,
      color: a.severity === "EXPIRED" ? "red" : a.severity === "URGENT" ? "red" : "gold",
      text: `${a.name_cn} 批号${a.batch_no} ${
        a.days_to_expiry < 0 ? `已过期${-a.days_to_expiry}天` : `${a.days_to_expiry}天后过期`
      }`,
    })),
    ...lowStock.slice(0, 3).map((a) => ({
      key: `l${a.material_id}`,
      color: "gold",
      text: `${a.name_cn} 低于安全库存(现 ${a.total_qty}/${a.safety_stock} ${a.unit})`,
    })),
  ].slice(0, 6);

  const equipmentPreview = (eqpAlerts as EquipmentAlert[]).slice(0, 6).map((a) => ({
    key: `${a.alert_type}-${a.equipment_id}-${a.due_date}`,
    color: a.severity === "red" ? "red" : "gold",
    text: `${a.name}(${a.equipment_code}) ${EQP_ALERT_TYPE[a.alert_type] ?? a.alert_type}${
      a.days_left < 0 ? `已过期${-a.days_left}天` : `还剩${a.days_left}天`
    }`,
  }));

  const alertsLoading = expiryLoading || lowLoading || eqpLoading;

  return (
    <>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        {greeting()}，{user?.full_name || user?.username}
      </Typography.Title>

      <Row gutter={[16, 16]}>
        {/* 关键统计 */}
        <Col xs={24} md={8}>
          <Card title="关键统计" size="small" style={{ height: "100%" }}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="物料" value={stats?.material_count ?? "—"} />
              </Col>
              <Col span={8}>
                <Statistic title="设备" value={stats?.equipment_count ?? "—"} />
              </Col>
              <Col span={8}>
                <Statistic title="活跃批次" value={stats?.active_batch_count ?? "—"} />
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 待处理告警汇总 */}
        <Col xs={24} md={8}>
          <Card
            title="待处理告警"
            size="small"
            style={{ height: "100%" }}
            extra={
              <Button type="link" size="small" onClick={() => navigate("/alerts")}>
                预警中心 <RightOutlined />
              </Button>
            }
          >
            {alertsLoading ? (
              <Spin size="small" />
            ) : (
              <Space direction="vertical" size={4}>
                <span><Tag color="red">{expired}</Tag>批次已过期</span>
                <span><Tag color="gold">{nearExpiry}</Tag>批次临近过期(90天内)</span>
                <span><Tag color="gold">{lowStock.length}</Tag>物料低库存</span>
                <span><Tag color="red">{eqpRed}</Tag>设备校验/维护/保修已过期或7天内</span>
                <span><Tag color="gold">{eqpYellow}</Tag>设备到期预警(30天内)</span>
              </Space>
            )}
          </Card>
        </Col>

        {/* 快捷入口 */}
        <Col xs={24} md={8}>
          <Card title="快捷入口" size="small" style={{ height: "100%" }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              {canWrite() && (
                <>
                  <Button block icon={<ImportOutlined />} onClick={() => navigate("/intake")}>
                    入库登记
                  </Button>
                  <Button block icon={<ExportOutlined />} onClick={() => navigate("/outgoing")}>
                    出库登记
                  </Button>
                </>
              )}
              {canEquip && (
                <Button block icon={<PlusOutlined />} onClick={() => navigate("/equipment")}>
                  新增设备 / 记录校验
                </Button>
              )}
              <Button block icon={<SafetyCertificateOutlined />} onClick={() => navigate("/stock")}>
                库存查询
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 物料预警概览 */}
        <Col xs={24} md={12}>
          <Card
            title={<><AlertOutlined /> 物料预警概览</>}
            size="small"
            extra={
              <Button type="link" size="small" onClick={() => navigate("/alerts")}>
                查看全部 <RightOutlined />
              </Button>
            }
          >
            <List
              size="small"
              loading={expiryLoading || lowLoading}
              dataSource={materialPreview}
              locale={{ emptyText: "暂无物料预警 🎉" }}
              renderItem={(item) => (
                <List.Item style={{ padding: "6px 0" }}>
                  <Tag color={item.color} style={{ marginRight: 8 }}>●</Tag>
                  {item.text}
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* 设备预警概览 */}
        <Col xs={24} md={12}>
          <Card
            title={<><AlertOutlined /> 设备预警概览</>}
            size="small"
            extra={
              <Button type="link" size="small" onClick={() => navigate("/alerts")}>
                查看全部 <RightOutlined />
              </Button>
            }
          >
            <List
              size="small"
              loading={eqpLoading}
              dataSource={equipmentPreview}
              locale={{ emptyText: "暂无设备预警 🎉" }}
              renderItem={(item) => (
                <List.Item style={{ padding: "6px 0" }}>
                  <Tag color={item.color} style={{ marginRight: 8 }}>●</Tag>
                  {item.text}
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
