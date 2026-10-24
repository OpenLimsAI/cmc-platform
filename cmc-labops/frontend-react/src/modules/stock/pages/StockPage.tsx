import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Typography, Table, Input, Select, Tabs, Tag, Space } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { stockByMaterial, stockByBatch } from "../../../api/inventory";
import MaterialDetailModal from "../components/MaterialDetailModal";

const TYPE_OPTIONS = [
  { label: "全部", value: "" },
  { label: "试剂", value: "reagent" },
  { label: "耗材", value: "consumable" },
  { label: "标准品", value: "standard" },
  { label: "色谱柱", value: "column" },
];

export default function StockPage() {
  const [tab, setTab] = useState("material");
  const [keyword, setKeyword] = useState("");
  const [materialType, setMaterialType] = useState("");
  const [detailId, setDetailId] = useState<number | null>(null);

  const { data: materialStock = [], isLoading: matLoading } = useQuery({
    queryKey: ["stockByMaterial", keyword, materialType],
    queryFn: () =>
      stockByMaterial({
        keyword: keyword || undefined,
        material_type: materialType || undefined,
      }).then((r) => r.data),
    enabled: tab === "material",
  });

  const { data: batchStock = [], isLoading: batchLoading } = useQuery({
    queryKey: ["stockByBatch", keyword, materialType],
    queryFn: () =>
      stockByBatch({
        keyword: keyword || undefined,
        material_type: materialType || undefined,
      }).then((r) => r.data),
    enabled: tab === "batch",
  });

  return (
    <>
      <Typography.Title level={4}>库存查询</Typography.Title>
      <Typography.Text type="secondary" style={{ display: "block", marginTop: -8, marginBottom: 12 }}>
        双击任一行查看物料详情与存放位置
      </Typography.Text>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索编码/名称/批号"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 280 }}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <Select
          options={TYPE_OPTIONS}
          value={materialType}
          onChange={setMaterialType}
          style={{ width: 120 }}
        />
      </Space>

      <Tabs activeKey={tab} onChange={setTab} items={[
        {
          key: "material",
          label: "按物料",
          children: (
            <Table
              rowKey="material_id"
              size="small"
              loading={matLoading}
              dataSource={materialStock}
              pagination={{ pageSize: 50 }}
              scroll={{ x: 1000 }}
              onRow={(r) => ({
                onDoubleClick: () => setDetailId(r.material_id),
                style: { cursor: "pointer" },
              })}
              columns={[
                { title: "物料编码", dataIndex: "material_code", width: 120 },
                { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
                { title: "生产商", dataIndex: "manufacturer", width: 120, ellipsis: true },
                { title: "规格型号", dataIndex: "spec_model", width: 150, ellipsis: true },
                // 标准品专属:在库批次的分装规格(多种时顿号分隔),仅筛选"标准品"时显示
                ...(materialType === "standard"
                  ? [{ title: "分装规格", dataIndex: "aliquot_specs", width: 160, ellipsis: true,
                       render: (v: string | null) => v || "—" }]
                  : []),
                { title: "单位", dataIndex: "unit", width: 60 },
                {
                  title: "总库存",
                  dataIndex: "total_qty",
                  width: 100,
                  sorter: (a, b) => Number(a.total_qty) - Number(b.total_qty),
                },
                {
                  title: "安全库存",
                  dataIndex: "safety_stock",
                  width: 100,
                },
                {
                  title: "状态",
                  width: 80,
                  render: (_, r) =>
                    r.low_stock ? (
                      <Tag color="red">低库存</Tag>
                    ) : (
                      <Tag color="green">正常</Tag>
                    ),
                },
              ]}
            />
          ),
        },
        {
          key: "batch",
          label: "按批次",
          children: (
            <Table
              rowKey="batch_id"
              size="small"
              loading={batchLoading}
              dataSource={batchStock}
              pagination={{ pageSize: 50 }}
              scroll={{ x: 1200 }}
              onRow={(r) => ({
                onDoubleClick: () => setDetailId(r.material_id),
                style: { cursor: "pointer" },
              })}
              columns={[
                { title: "物料编码", dataIndex: "material_code", width: 120 },
                { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
                { title: "批号", dataIndex: "batch_no", width: 140 },
                { title: "分装规格", dataIndex: "aliquot_spec", width: 110, render: (v: string | null) => v || "—" },
                { title: "位置", dataIndex: "location_name", width: 160 },
                { title: "单位", dataIndex: "unit", width: 60 },
                {
                  title: "当前库存",
                  dataIndex: "current_qty",
                  width: 100,
                },
                {
                  title: "有效期",
                  dataIndex: "expiry_date",
                  width: 110,
                  render: (v: string | null, r) => {
                    if (!v) return "-";
                    const d = r.days_to_expiry ?? 999;
                    return (
                      <Tag color={d < 0 ? "red" : d <= 30 ? "orange" : "default"}>
                        {v}
                      </Tag>
                    );
                  },
                },
              ]}
            />
          ),
        },
      ]} />

      <MaterialDetailModal
        materialId={detailId}
        open={detailId != null}
        onClose={() => setDetailId(null)}
      />
    </>
  );
}
