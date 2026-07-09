import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Typography, Card, Form, InputNumber, DatePicker, Input, Radio,
  Button, message, Table, Tag, Alert,
} from "antd";
import dayjs from "dayjs";
import {
  stockByBatch, adjustStock, type StockByBatch,
} from "../../../api/inventory";
import { getErrorDetail } from "../../../shared/errors";

type Mode = "actual" | "delta";

export default function AdjustPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<StockByBatch | null>(null);
  const [mode, setMode] = useState<Mode>("actual");
  const [form] = Form.useForm();
  const inputValue = Form.useWatch("value", form) as number | undefined;

  const { data: batches = [], isLoading, refetch } = useQuery({
    queryKey: ["stockByBatch", "adjust", keyword],
    queryFn: () =>
      stockByBatch({ keyword: keyword || undefined }).then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: { batch_id: number; qty: number; txn_date: string; remark?: string }) =>
      adjustStock(data),
    onSuccess: () => {
      message.success("盘点调整成功");
      setSelectedBatch(null);
      form.resetFields();
      refetch();
    },
    onError: (err: unknown) => {
      const detail =
        getErrorDetail(err, "调整失败");
      message.error(detail);
    },
  });

  // 后端 Decimal 序列化到前端是字符串,直接用 + 会变成字符串拼接(页面崩溃/校验失效),必须先 Number()
  const bookQty = Number(selectedBatch?.current_qty ?? 0);

  // 按实际盘点数: delta = 实际数 - 当前库存;按调整量: delta = 输入值
  const computeDelta = (value: number): number =>
    mode === "actual" ? Number((value - bookQty).toFixed(2)) : value;

  const handleSubmit = async () => {
    if (!selectedBatch) return;
    const values = await form.validateFields();
    const delta = computeDelta(values.value);
    if (delta === 0) {
      message.info("调整量为 0,无需调整");
      return;
    }
    mutation.mutate({
      batch_id: selectedBatch.batch_id,
      qty: delta,
      txn_date: values.txn_date.format("YYYY-MM-DD"),
      remark: values.remark,
    });
  };

  const previewDelta =
    selectedBatch && typeof inputValue === "number" ? computeDelta(inputValue) : null;

  return (
    <>
      <Typography.Title level={4}>盘点调整</Typography.Title>
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
          onClick: () => setSelectedBatch(record),
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
            render: (v: string | null, r: StockByBatch) => {
              if (!v) return "-";
              const d = r.days_to_expiry ?? 0;
              return (
                <Tag color={d < 0 ? "red" : d <= 30 ? "orange" : "default"}>
                  {v}
                </Tag>
              );
            },
          },
        ]}
      />

      {selectedBatch && (
        <Card
          title={`盘点调整: ${selectedBatch.material_code} / ${selectedBatch.batch_no}（账面: ${selectedBatch.current_qty} ${selectedBatch.unit}）`}
          style={{ marginTop: 16, maxWidth: 560 }}
        >
          <Radio.Group
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as Mode);
              form.resetFields(["value"]);
            }}
            style={{ marginBottom: 16 }}
          >
            <Radio.Button value="actual">按实际盘点数</Radio.Button>
            <Radio.Button value="delta">按调整量(±)</Radio.Button>
          </Radio.Group>
          <Form form={form} layout="vertical" initialValues={{ txn_date: dayjs() }}>
            <Form.Item
              name="value"
              label={mode === "actual" ? "实际盘点数" : "调整量(正为盘盈,负为盘亏)"}
              rules={[
                { required: true, message: "请输入数量" },
                {
                  validator: (_, v) =>
                    typeof v === "number" && bookQty + computeDelta(v) < 0
                      ? Promise.reject(new Error("调整后库存不得为负"))
                      : Promise.resolve(),
                },
              ]}
            >
              <InputNumber
                min={mode === "actual" ? 0 : undefined}
                style={{ width: "100%" }}
              />
            </Form.Item>
            {previewDelta !== null && (
              <Alert
                style={{ marginBottom: 16 }}
                type={previewDelta === 0 ? "info" : previewDelta > 0 ? "success" : "warning"}
                message={`调整量: ${previewDelta > 0 ? "+" : ""}${previewDelta} ${selectedBatch.unit} → 调整后库存: ${Number((bookQty + previewDelta).toFixed(2))} ${selectedBatch.unit}`}
              />
            )}
            <Form.Item name="txn_date" label="盘点日期" rules={[{ required: true }]}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="remark" label="备注(盘盈盘亏原因)">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Button type="primary" loading={mutation.isPending} onClick={handleSubmit}>
              确认调整
            </Button>
          </Form>
        </Card>
      )}
    </>
  );
}
