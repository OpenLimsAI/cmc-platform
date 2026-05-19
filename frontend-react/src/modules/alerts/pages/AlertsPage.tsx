import { useQuery } from "@tanstack/react-query";
import { Typography, Table, Tag, Tabs } from "antd";
import { expiryAlerts, lowStockAlerts } from "../../../api/inventory";

export default function AlertsPage() {
  const { data: expiry = [], isLoading: expiryLoading } = useQuery({
    queryKey: ["expiryAlerts"],
    queryFn: () => expiryAlerts(90).then((r) => r.data),
  });

  const { data: lowStock = [], isLoading: lowLoading } = useQuery({
    queryKey: ["lowStockAlerts"],
    queryFn: () => lowStockAlerts().then((r) => r.data),
  });

  return (
    <>
      <Typography.Title level={4}>库存预警</Typography.Title>
      <Tabs items={[
        {
          key: "expiry",
          label: `有效期预警 (${expiry.length})`,
          children: (
            <Table
              rowKey="batch_id"
              size="small"
              loading={expiryLoading}
              dataSource={expiry}
              pagination={{ pageSize: 50 }}
              columns={[
                { title: "物料编码", dataIndex: "material_code", width: 120 },
                { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
                { title: "批号", dataIndex: "batch_no", width: 140 },
                { title: "有效期", dataIndex: "expiry_date", width: 110 },
                {
                  title: "剩余天数",
                  dataIndex: "days_to_expiry",
                  width: 100,
                  sorter: (a: Record<string, number>, b: Record<string, number>) => a.days_to_expiry - b.days_to_expiry,
                },
                {
                  title: "严重度",
                  dataIndex: "severity",
                  width: 100,
                  render: (v: string) => {
                    const m: Record<string, { color: string; text: string }> = {
                      EXPIRED: { color: "red", text: "已过期" },
                      URGENT: { color: "orange", text: "紧急" },
                      WARNING: { color: "gold", text: "预警" },
                    };
                    const t = m[v];
                    return t ? <Tag color={t.color}>{t.text}</Tag> : v;
                  },
                },
                { title: "当前库存", dataIndex: "current_qty", width: 100 },
                { title: "位置", dataIndex: "location_name", width: 160 },
              ]}
            />
          ),
        },
        {
          key: "lowstock",
          label: `低库存预警 (${lowStock.length})`,
          children: (
            <Table
              rowKey="material_id"
              size="small"
              loading={lowLoading}
              dataSource={lowStock}
              pagination={{ pageSize: 50 }}
              columns={[
                { title: "物料编码", dataIndex: "material_code", width: 120 },
                { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
                { title: "单位", dataIndex: "unit", width: 60 },
                { title: "安全库存", dataIndex: "safety_stock", width: 100 },
                { title: "当前库存", dataIndex: "total_qty", width: 100 },
                {
                  title: "缺口",
                  dataIndex: "gap",
                  width: 100,
                  render: (v: number) => <Tag color="red">{v}</Tag>,
                },
              ]}
            />
          ),
        },
      ]} />
    </>
  );
}
