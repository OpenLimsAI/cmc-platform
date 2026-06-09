import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Typography, Card, Form, InputNumber, DatePicker, Input,
  Button, message, Table, Tag, Alert, Descriptions,
} from "antd";
import dayjs from "dayjs";
import {
  stockByBatch, outgoing, type StockByBatch, type TxnOutRequest,
} from "../../../api/inventory";
import { listBatchCells, releaseCells, type BatchCell } from "../../../api/storage";
import { getErrorDetail } from "../../../shared/errors";

function expiryTag(v: string | null, days: number | null) {
  if (!v) return <span style={{ color: "#8c8c8c" }}>—</span>;
  const d = days ?? 999;
  return <Tag color={d < 0 ? "red" : d <= 30 ? "orange" : "default"}>{v}</Tag>;
}

export default function OutgoingPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<StockByBatch | null>(null);
  const [selectedCellIds, setSelectedCellIds] = useState<number[]>([]);
  const [form] = Form.useForm();
  const qc = useQueryClient();

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
      if (selectedCellIds.length === 0) { message.warning("请勾选要取走的孔位"); return; }
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
        ]}
      />

      {selectedBatch && (
        <Card
          title={`出库: ${selectedBatch.material_code} / 批号 ${selectedBatch.batch_no}`}
          style={{ marginTop: 16, maxWidth: isCellBatch ? 760 : 520 }}
        >
          <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
            <Descriptions.Item label="位置">{selectedBatch.location_name}</Descriptions.Item>
            <Descriptions.Item label="当前库存">{selectedBatch.current_qty} {selectedBatch.unit}</Descriptions.Item>
          </Descriptions>

          {isCellBatch && (
            <Alert
              type="info" showIcon style={{ marginBottom: 12 }}
              message="该批次按 -80℃ 孔位存放,请勾选要取走的具体孔位(精确定位)。"
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
                    { title: "样品", dataIndex: "sample_label", width: 140, render: (v: string | null) => v || "—" },
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
      )}
    </>
  );
}
