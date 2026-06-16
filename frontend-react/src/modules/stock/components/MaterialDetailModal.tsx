import { useQuery } from "@tanstack/react-query";
import { Modal, Descriptions, Table, Tag, Typography, Spin, Empty } from "antd";
import { getMaterial, TT_INTERNAL_CODE } from "../../../api/materials";
import { stockByBatch, type StockByBatch } from "../../../api/inventory";
import { listBatchCells } from "../../../api/storage";

// 有效期色标(与库存/出库页一致)
function expiryTag(v: string | null, days: number | null) {
  if (!v) return <span style={{ color: "#8c8c8c" }}>—</span>;
  const d = days ?? 999;
  return <Tag color={d < 0 ? "red" : d <= 30 ? "orange" : "default"}>{v}</Tag>;
}

// 某批次的孔位明细(展开懒加载;空 = 散放)
function BatchCells({ batchId }: { batchId: number }) {
  const { data: cells = [], isLoading } = useQuery({
    queryKey: ["batch-cells", batchId],
    queryFn: () => listBatchCells(batchId).then((r) => r.data),
  });
  if (isLoading) return <Spin size="small" />;
  if (cells.length === 0) return <Typography.Text type="secondary">散放(无独立孔位)</Typography.Text>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {cells.map((c) => (
        <Tag key={c.cell_node_id} color={c.days_to_expiry != null && c.days_to_expiry < 0 ? "red" : "green"}>
          {c.address}{c.sample_label ? ` · ${c.sample_label}` : ""}
        </Tag>
      ))}
    </div>
  );
}

interface Props {
  materialId: number | null;
  open: boolean;
  onClose: () => void;
}

export default function MaterialDetailModal({ materialId, open, onClose }: Props) {
  const { data: material, isLoading: matLoading } = useQuery({
    queryKey: ["material", materialId],
    queryFn: () => getMaterial(materialId!).then((r) => r.data),
    enabled: open && materialId != null,
  });
  const { data: batches = [], isLoading: batchLoading } = useQuery({
    queryKey: ["stockByBatch", "material", materialId],
    queryFn: () => stockByBatch({ material_id: materialId, only_positive: true }).then((r) => r.data),
    enabled: open && materialId != null,
  });

  return (
    <Modal
      title="物料详情"
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
    >
      {matLoading ? (
        <Spin />
      ) : !material ? (
        <Empty description="未找到物料" />
      ) : (
        <>
          <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
            <Descriptions.Item label="物料ID">
              <span style={{ color: "#8c8c8c" }}>{material.material_id}</span>
            </Descriptions.Item>
            <Descriptions.Item label="物料编码">
              {material.material_code === TT_INTERNAL_CODE ? <Tag color="orange">无编码</Tag> : material.material_code}
            </Descriptions.Item>
            <Descriptions.Item label="物料名称">{material.name_cn}</Descriptions.Item>
            <Descriptions.Item label="生产商">{material.manufacturer ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="规格型号">{material.spec_model ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="货号">{material.catalog_no ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="单位">{material.unit}</Descriptions.Item>
            <Descriptions.Item label="级别">{material.grade ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="分类">{material.category ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="来源">
              {material.data_source === "mdm" ? <Tag color="geekblue">MDM</Tag> : <Tag>本地</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="安全库存">{material.safety_stock}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {material.is_active ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>}
            </Descriptions.Item>
          </Descriptions>

          <Typography.Title level={5} style={{ marginTop: 20 }}>
            库存分布(各批次 / 位置)
          </Typography.Title>
          <Table<StockByBatch>
            rowKey="batch_id"
            size="small"
            loading={batchLoading}
            dataSource={batches}
            pagination={false}
            locale={{ emptyText: "暂无在库批次" }}
            expandable={{
              expandedRowRender: (r) => <BatchCells batchId={r.batch_id} />,
              rowExpandable: () => true,
            }}
            columns={[
              { title: "批号", dataIndex: "batch_no", width: 160 },
              { title: "位置", dataIndex: "location_name", width: 180 },
              {
                title: "当前库存",
                dataIndex: "current_qty",
                width: 110,
                render: (v: number) => `${v} ${material.unit}`,
              },
              { title: "收货日期", dataIndex: "received_date", width: 120 },
              {
                title: "入库人",
                dataIndex: "intake_operator_name",
                width: 100,
                render: (v: string | null) => v || "—",
              },
              {
                title: "有效期",
                dataIndex: "expiry_date",
                width: 120,
                render: (v: string | null, r) => expiryTag(v, r.days_to_expiry),
              },
            ]}
          />
        </>
      )}
    </Modal>
  );
}
