import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Typography, Card, Form, InputNumber, DatePicker, Input,
  Button, message, Table, Tag, Alert, Descriptions, Segmented, Empty, Spin,
} from "antd";
import dayjs from "dayjs";
import {
  stockByBatch, outgoing, type StockByBatch, type TxnOutRequest,
} from "../../../api/inventory";
import {
  listBatchCells, releaseCells, listCells, listAncestors, type BatchCell,
} from "../../../api/storage";
import CellGrid from "../../storage/components/CellGrid";
import { getErrorDetail } from "../../../shared/errors";
import { useAuthStore } from "../../../stores/authStore";
import BatchEditModal from "../components/BatchEditModal";

function expiryTag(v: string | null, days: number | null) {
  if (!v) return <span style={{ color: "#8c8c8c" }}>—</span>;
  const d = days ?? 999;
  return <Tag color={d < 0 ? "red" : d <= 30 ? "orange" : "default"}>{v}</Tag>;
}

const NODE_LABEL: Record<string, string> = {
  FRIDGE: "冰箱", RACK: "冻存架", RACK_LAYER: "层", BOX: "盒",
};

/** 出库右栏:本批次的冻存盒可视化。按盒切换(只限本批次的盒),点本批次的孔即选中/取消(与左侧勾选同步)。 */
function BatchBoxView({
  batchId, batchCells, selectedIds, toggle,
}: {
  batchId: number;
  batchCells: BatchCell[];
  selectedIds: number[];
  toggle: (cellId: number) => void;
}) {
  // 本批次占用的盒(去重),标签取该盒任一孔地址的"盒"部分(逗号前)
  const boxes = useMemo(() => {
    const m = new Map<number, { boxId: number; label: string; count: number }>();
    batchCells.forEach((c) => {
      if (c.box_node_id == null) return;
      const e = m.get(c.box_node_id);
      if (e) e.count += 1;
      else m.set(c.box_node_id, { boxId: c.box_node_id, label: c.address.split(",")[0], count: 1 });
    });
    return [...m.values()];
  }, [batchCells]);

  const [boxId, setBoxId] = useState<number | undefined>(boxes[0]?.boxId);
  const activeBox = boxId ?? boxes[0]?.boxId;

  const { data: ancestors = [] } = useQuery({
    queryKey: ["ancestors", activeBox],
    queryFn: () => listAncestors(activeBox!).then((r) => r.data),
    enabled: activeBox != null,
  });
  const { data: cells = [], isLoading } = useQuery({
    queryKey: ["box-cells", activeBox],
    queryFn: () => listCells(activeBox!).then((r) => r.data),
    enabled: activeBox != null,
  });

  if (!boxes.length) return <Empty description="无孔位" />;

  const crumb = ["FRIDGE", "RACK", "RACK_LAYER", "BOX"]
    .map((t) => ancestors.find((n) => n.node_type === t))
    .filter(Boolean)
    .map((n) => `${NODE_LABEL[n!.node_type]} ${n!.label || n!.code}`)
    .join(" › ");

  return (
    <>
      {crumb && <div style={{ marginBottom: 10, color: "#555" }}>{crumb}</div>}
      {boxes.length > 1 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: "#888", marginRight: 8 }}>本批次分布在 {boxes.length} 个盒,选择:</span>
          <Segmented
            value={activeBox}
            onChange={(v) => setBoxId(v as number)}
            options={boxes.map((b) => ({ label: `${b.label}(${b.count})`, value: b.boxId }))}
          />
        </div>
      )}
      {isLoading ? (
        <Spin />
      ) : (
        <>
          <CellGrid
            cells={cells}
            ownBatchId={batchId}
            selectedIds={new Set(selectedIds)}
            onCellClick={(c) => toggle(c.cell_node_id)}
          />
          <div style={{ marginTop: 10, color: "#888", fontSize: 12 }}>
            绿=本批次(可点选取走) · 蓝=已选 · 暗灰=其它物料 · 浅灰=空孔
          </div>
        </>
      )}
    </>
  );
}

export default function OutgoingPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<StockByBatch | null>(null);
  const [selectedCellIds, setSelectedCellIds] = useState<number[]>([]);
  const [editBatchId, setEditBatchId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const qc = useQueryClient();
  const canWrite = useAuthStore((s) => s.canWrite());

  const { data: batches = [], isLoading, refetch } = useQuery({
    queryKey: ["stockByBatch", keyword],
    queryFn: () =>
      stockByBatch({ keyword: keyword || undefined, only_positive: true }).then((r) => r.data),
  });

  // 选中批次后查它占用的孔:非空 = -80 孔位批次(按孔出库), 空 = 散放(按数量出库)
  const { data: batchCells = [] } = useQuery({
    queryKey: ["batch-cells", selectedBatch?.batch_id],
    queryFn: () => listBatchCells(selectedBatch!.batch_id).then((r) => r.data),
    enabled: !!selectedBatch,
  });
  const isCellBatch = batchCells.length > 0;

  const pickBatch = (b: StockByBatch) => {
    setSelectedBatch(b);
    setSelectedCellIds([]);
    form.resetFields();
  };
  const toggleCell = (cellId: number) =>
    setSelectedCellIds((ids) => (ids.includes(cellId) ? ids.filter((x) => x !== cellId) : [...ids, cellId]));

  const finishOk = () => {
    setSelectedBatch(null);
    setSelectedCellIds([]);
    form.resetFields();
    refetch();
    qc.invalidateQueries({ queryKey: ["batch-cells"] });
    qc.invalidateQueries({ queryKey: ["box-cells"] });
  };

  const outMut = useMutation({
    mutationFn: (data: TxnOutRequest) => outgoing(data),
    onSuccess: () => { message.success("出库成功"); finishOk(); },
    onError: (err: unknown) => message.error(getErrorDetail(err, "出库失败")),
  });

  const releaseMut = useMutation({
    mutationFn: releaseCells,
    onSuccess: (res) => { message.success(`已出库 ${res.data.count} 管(已释放孔位)`); finishOk(); },
    onError: (err: unknown) => message.error(getErrorDetail(err, "出库失败")),
  });

  const handleSubmit = async () => {
    if (!selectedBatch) return;
    const values = await form.validateFields();
    const txn_date = values.txn_date.format("YYYY-MM-DD");
    if (isCellBatch) {
      if (selectedCellIds.length === 0) { message.warning("请勾选/点选要取走的孔位"); return; }
      releaseMut.mutate({
        cell_node_ids: selectedCellIds, txn_date,
        purpose: values.purpose, remark: values.remark,
      });
    } else {
      outMut.mutate({
        batch_id: selectedBatch.batch_id,
        qty: values.qty,
        txn_date,
        purpose: values.purpose,
        remark: values.remark,
      });
    }
  };

  const pending = outMut.isPending || releaseMut.isPending;

  return (
    <>
      <Typography.Title level={4}>出库登记</Typography.Title>
      <Input.Search
        placeholder="搜索物料编码/名称/批号"
        style={{ width: 360, marginBottom: 16 }}
        onSearch={setKeyword}
        allowClear
      />
      <Table
        rowKey="batch_id"
        size="small"
        loading={isLoading}
        dataSource={batches}
        pagination={{ pageSize: 20 }}
        onRow={(record) => ({
          onClick: () => pickBatch(record),
          style: {
            cursor: "pointer",
            background:
              selectedBatch?.batch_id === record.batch_id ? "#e6f4ff" : undefined,
          },
        })}
        columns={[
          { title: "物料编码", dataIndex: "material_code", width: 120 },
          { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
          { title: "批号", dataIndex: "batch_no", width: 140 },
          {
            title: "原研药批号",
            dataIndex: "originator_batch_no",
            width: 140,
            render: (v: string | null) => v || "—",
          },
          { title: "位置", dataIndex: "location_name", width: 160 },
          {
            title: "当前库存",
            dataIndex: "current_qty",
            width: 100,
            render: (v: number, r: StockByBatch) => `${v} ${r.unit}`,
          },
          {
            title: "有效期",
            dataIndex: "expiry_date",
            width: 110,
            render: (v: string | null, r: StockByBatch) => expiryTag(v, r.days_to_expiry),
          },
          ...(canWrite
            ? [{
                title: "操作",
                key: "action",
                width: 80,
                render: (_: unknown, r: StockByBatch) => (
                  <Button
                    type="link"
                    size="small"
                    onClick={(e) => { e.stopPropagation(); setEditBatchId(r.batch_id); }}
                  >
                    编辑
                  </Button>
                ),
              }]
            : []),
        ]}
      />

      {selectedBatch && (
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start", marginTop: 16 }}>
          <Card
            title={`出库: ${selectedBatch.material_code} / 批号 ${selectedBatch.batch_no}`}
            style={{ flex: isCellBatch ? "1 1 520px" : "0 1 520px", minWidth: 420 }}
          >
            <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="位置">{selectedBatch.location_name}</Descriptions.Item>
              <Descriptions.Item label="当前库存">{selectedBatch.current_qty} {selectedBatch.unit}</Descriptions.Item>
            </Descriptions>

            {isCellBatch && (
              <Alert
                type="info" showIcon style={{ marginBottom: 12 }}
                message="该批次按 -80℃ 孔位存放,可在右侧盒图点选,或在下表勾选要取走的孔位(两者同步)。"
              />
            )}

            <Form form={form} layout="vertical" initialValues={{ txn_date: dayjs() }}>
              {isCellBatch ? (
                <Form.Item label={`选择取走的孔位(已选 ${selectedCellIds.length} / 共 ${batchCells.length} 管)`} required>
                  <Table<BatchCell>
                    rowKey="cell_node_id"
                    size="small"
                    dataSource={batchCells}
                    pagination={false}
                    scroll={{ y: 280 }}
                    rowSelection={{
                      selectedRowKeys: selectedCellIds,
                      onChange: (keys) => setSelectedCellIds(keys as number[]),
                    }}
                    columns={[
                      { title: "孔位地址", dataIndex: "address" },
                      { title: "样品", dataIndex: "sample_label", width: 120, render: (v: string | null) => v || "—" },
                      {
                        title: "有效期",
                        dataIndex: "expiry_date",
                        width: 120,
                        render: (v: string | null, r) => expiryTag(v, r.days_to_expiry),
                      },
                    ]}
                  />
                </Form.Item>
              ) : (
                <Form.Item
                  name="qty"
                  label={`出库数量(当前库存: ${selectedBatch.current_qty} ${selectedBatch.unit})`}
                  rules={[{ required: true }]}
                >
                  <InputNumber min={0.01} max={selectedBatch.current_qty} style={{ width: "100%" }} />
                </Form.Item>
              )}
              <Form.Item name="txn_date" label="出库日期" rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="purpose" label="用途">
                <Input />
              </Form.Item>
              <Form.Item name="remark" label="备注">
                <Input.TextArea rows={2} />
              </Form.Item>
              <Button type="primary" loading={pending} onClick={handleSubmit}>
                确认出库
              </Button>
            </Form>
          </Card>

          {isCellBatch && (
            <Card title="冻存盒可视化" style={{ flex: "1 1 480px", minWidth: 360 }}>
              <BatchBoxView
                key={selectedBatch.batch_id}
                batchId={selectedBatch.batch_id}
                batchCells={batchCells}
                selectedIds={selectedCellIds}
                toggle={toggleCell}
              />
            </Card>
          )}
        </div>
      )}

      <BatchEditModal
        batchId={editBatchId}
        open={editBatchId != null}
        onClose={() => setEditBatchId(null)}
        onSuccess={() => { setEditBatchId(null); refetch(); }}
      />
    </>
  );
}
