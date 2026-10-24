import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Typography, Card, Form, InputNumber, DatePicker, Input, Select,
  Button, message, Table, Tag,
} from "antd";
import dayjs from "dayjs";
import {
  stockByBatch, transferBatch, listLocations,
  type StockByBatch, type Location,
} from "../../../api/inventory";
import { getErrorDetail } from "../../../shared/errors";

export default function TransferPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<StockByBatch | null>(null);
  const [form] = Form.useForm();

  const { data: batches = [], isLoading, refetch } = useQuery({
    queryKey: ["stockByBatch", "transfer", keyword],
    queryFn: () =>
      stockByBatch({ keyword: keyword || undefined, only_positive: true }).then(
        (r) => r.data,
      ),
  });

  const { data: locations = [] } = useQuery({
    queryKey: ["locations"],
    queryFn: () => listLocations().then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: {
      source_batch_id: number;
      dest_location_id: number;
      qty: number;
      txn_date: string;
      remark?: string;
    }) => transferBatch(data),
    onSuccess: () => {
      message.success("移库成功(源 OUT + 目标 IN 两条流水已记录)");
      setSelectedBatch(null);
      form.resetFields();
      refetch();
    },
    onError: (err: unknown) => {
      const detail =
        getErrorDetail(err, "移库失败");
      message.error(detail);
    },
  });

  const handleSubmit = async () => {
    if (!selectedBatch) return;
    const values = await form.validateFields();
    mutation.mutate({
      source_batch_id: selectedBatch.batch_id,
      dest_location_id: values.dest_location_id,
      qty: values.qty,
      txn_date: values.txn_date.format("YYYY-MM-DD"),
      remark: values.remark,
    });
  };

  return (
    <>
      <Typography.Title level={4}>移库</Typography.Title>
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
          { title: "当前位置", dataIndex: "location_name", width: 160 },
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
          title={`移库: ${selectedBatch.material_code} / ${selectedBatch.batch_no}（当前位置: ${selectedBatch.location_name}）`}
          style={{ marginTop: 16, maxWidth: 560 }}
        >
          <Form form={form} layout="vertical" initialValues={{ txn_date: dayjs() }}>
            <Form.Item
              name="dest_location_id"
              label="目标位置"
              rules={[
                { required: true, message: "请选择目标位置" },
                {
                  validator: (_, v) =>
                    v === selectedBatch.location_id
                      ? Promise.reject(new Error("目标位置不能与当前位置相同"))
                      : Promise.resolve(),
                },
              ]}
            >
              <Select
                showSearch
                optionFilterProp="label"
                placeholder="选择目标位置"
                options={locations.map((l: Location) => ({
                  value: l.location_id,
                  label: l.name,
                }))}
              />
            </Form.Item>
            <Form.Item
              name="qty"
              label={`移库数量（当前库存: ${selectedBatch.current_qty} ${selectedBatch.unit}）`}
              rules={[{ required: true }]}
            >
              <InputNumber
                min={0.01}
                max={Number(selectedBatch.current_qty)}
                style={{ width: "100%" }}
              />
            </Form.Item>
            <Form.Item name="txn_date" label="移库日期" rules={[{ required: true }]}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="remark" label="备注">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Button type="primary" loading={mutation.isPending} onClick={handleSubmit}>
              确认移库
            </Button>
          </Form>
        </Card>
      )}
    </>
  );
}
