import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Card, Form, Segmented, DatePicker, Select, Input, InputNumber, Button,
  Space, Typography, message, Alert, Tag, Divider,
} from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { listMaterials, type Material } from "../../../api/materials";
import { bulkIntake, type BulkIntakeResult } from "../../../api/inventory";
import { getErrorDetail } from "../../../shared/errors";
import LocationPicker from "../components/LocationPicker";

const TYPE_OPTIONS = [
  { label: "试剂", value: "reagent" },
  { label: "耗材", value: "consumable" },
  { label: "标准品", value: "standard" },
  { label: "色谱柱", value: "column" },
];

export default function BulkIntakePage({ embedded = false }: { embedded?: boolean }) {
  const [form] = Form.useForm();
  const [result, setResult] = useState<BulkIntakeResult | null>(null);

  const { data: materials = [] } = useQuery({
    queryKey: ["materials", "active-all"],
    queryFn: () => listMaterials().then((r) => r.data),
  });
  const materialOptions = materials
    .filter((m: Material) => m.is_active)
    .map((m: Material) => ({ label: `${m.material_code} ${m.name_cn}`, value: m.material_id }));

  const mutation = useMutation({
    mutationFn: bulkIntake,
    onSuccess: (res) => {
      setResult(res.data);
      if (res.data.ok) {
        message.success(`批量入库成功:新建 ${res.data.created} 条、追加 ${res.data.appended} 条`);
        form.resetFields();
        form.setFieldsValue?.({});
      } else {
        message.error(`有 ${res.data.failed} 行不合法,已整体取消,请修正后重试`);
      }
    },
    onError: (e) => message.error(getErrorDetail(e, "批量入库失败")),
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();
    setResult(null);
    mutation.mutate({
      received_date: values.received_date.format("YYYY-MM-DD"),
      intake_type: values.intake_type,
      rows: (values.rows ?? []).map((r: Record<string, unknown>) => ({
        material_id: r.material_id as number,
        batch_no: r.batch_no as string,
        expiry_date: r.expiry_date ? (r.expiry_date as dayjs.Dayjs).format("YYYY-MM-DD") : null,
        location_id: r.location_id as number,
        qty: r.qty as number,
      })),
    });
  };

  const rowError = (idx: number) =>
    result && !result.ok ? result.results.find((x) => x.index === idx && x.status === "error") : undefined;

  return (
    <>
      {!embedded && <Typography.Title level={4}>批量入库</Typography.Title>}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="多物料批量:一次录入多个不同物料(散放层),全部合法才写入(全有或全无)。-80℃ 冻存请用「单物料登记」按孔位入库。"
      />

      <Form
        form={form}
        layout="vertical"
        initialValues={{ intake_type: "reagent", received_date: dayjs(), rows: [{}] }}
      >
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space size="large" wrap>
            <Form.Item name="intake_type" label="入库类型" style={{ marginBottom: 0 }}>
              <Segmented options={TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item name="received_date" label="入库日期" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
              <DatePicker />
            </Form.Item>
          </Space>
        </Card>

        <Form.List name="rows">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field) => {
                const err = rowError(field.name);
                return (
                  <Card
                    key={field.key}
                    size="small"
                    style={{ marginBottom: 12, borderColor: err ? "#ff4d4f" : undefined }}
                  >
                    <Space align="start" wrap>
                      <Form.Item
                        {...field}
                        label="物料"
                        name={[field.name, "material_id"]}
                        rules={[{ required: true, message: "选物料" }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Select
                          showSearch
                          optionFilterProp="label"
                          placeholder="编码 / 名称"
                          options={materialOptions}
                          style={{ width: 240 }}
                        />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        label="批号"
                        name={[field.name, "batch_no"]}
                        rules={[{ required: true, message: "批号" }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Input style={{ width: 140 }} />
                      </Form.Item>
                      <Form.Item {...field} label="有效期" name={[field.name, "expiry_date"]} style={{ marginBottom: 0 }}>
                        <DatePicker style={{ width: 140 }} />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        label="数量"
                        name={[field.name, "qty"]}
                        rules={[{ required: true, message: "数量" }]}
                        style={{ marginBottom: 0 }}
                      >
                        <InputNumber min={0.01} style={{ width: 100 }} />
                      </Form.Item>
                      <Form.Item
                        {...field}
                        label="存放位置"
                        name={[field.name, "location_id"]}
                        rules={[{ required: true, message: "选位置" }]}
                        style={{ marginBottom: 0 }}
                      >
                        <LocationPicker />
                      </Form.Item>
                      <Form.Item label=" " style={{ marginBottom: 0 }}>
                        <Button
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => remove(field.name)}
                          disabled={fields.length === 1}
                        />
                      </Form.Item>
                    </Space>
                    {err && (
                      <div style={{ marginTop: 8 }}>
                        <Tag color="red">{err.message}</Tag>
                      </div>
                    )}
                  </Card>
                );
              })}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({})}>
                添加一行
              </Button>
            </>
          )}
        </Form.List>

        <Divider />
        {result?.ok && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 12 }}
            message={`成功:新建 ${result.created} 条、追加 ${result.appended} 条`}
          />
        )}
        <Button
          type="primary"
          size="large"
          loading={mutation.isPending}
          onClick={handleSubmit}
        >
          提交批量入库
        </Button>
      </Form>
    </>
  );
}
