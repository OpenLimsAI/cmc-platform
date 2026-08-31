import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Modal, Form, Input, InputNumber, DatePicker, Alert, Divider, Spin, message,
} from "antd";
import dayjs from "dayjs";
import {
  getBatch, updateBatchMeta, type Batch, type BatchMetaUpdate,
} from "../../../api/inventory";
import { getErrorDetail } from "../../../shared/errors";

/** 可编辑的元信息字段(与后端 BATCH_EDITABLE_FIELDS 对齐)。日期字段用 dayjs。 */
const DATE_FIELDS = ["expiry_date", "received_date", "aliquot_date"] as const;

type FormValues = {
  expiry_date?: dayjs.Dayjs | null;
  received_date?: dayjs.Dayjs | null;
  aliquot_date?: dayjs.Dayjs | null;
  remark?: string | null;
  concentration?: string | null;
  extinction_coefficient?: number | null;
  serial_no?: string | null;
  asset_no?: string | null;
  responsible_person?: string | null;
  project_no?: string | null;
  originator_batch_no?: string | null;
  aliquot_spec?: string | null;
  reviewer_username?: string;
  reviewer_password?: string;
};

function toForm(b: Batch): FormValues {
  return {
    expiry_date: b.expiry_date ? dayjs(b.expiry_date) : null,
    received_date: b.received_date ? dayjs(b.received_date) : null,
    aliquot_date: b.aliquot_date ? dayjs(b.aliquot_date) : null,
    remark: b.remark,
    concentration: b.concentration,
    extinction_coefficient: b.extinction_coefficient,
    serial_no: b.serial_no,
    asset_no: b.asset_no,
    responsible_person: b.responsible_person,
    project_no: b.project_no,
    originator_batch_no: b.originator_batch_no,
    aliquot_spec: b.aliquot_spec,
  };
}

/** 把一个字段值规整成可比较/可提交的形态(日期转 YYYY-MM-DD,空串转 null)。 */
function norm(field: string, v: unknown): string | number | null {
  if (v == null || v === "") return null;
  if ((DATE_FIELDS as readonly string[]).includes(field)) {
    return (v as dayjs.Dayjs).format("YYYY-MM-DD");
  }
  return v as string | number;
}

export default function BatchEditModal({
  batchId, open, onClose, onSuccess,
}: {
  batchId: number | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<FormValues>();

  const { data: batch, isLoading } = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId!).then((r) => r.data),
    enabled: open && batchId != null,
  });

  useEffect(() => {
    if (batch) form.setFieldsValue(toForm(batch));
  }, [batch, form]);

  const mut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: BatchMetaUpdate }) =>
      updateBatchMeta(id, data),
    onSuccess: () => { message.success("修改已保存(已复核签名)"); onSuccess(); },
    onError: (err: unknown) => message.error(getErrorDetail(err, "修改失败")),
  });

  const handleOk = async () => {
    if (!batch || batchId == null) return;
    const v = await form.validateFields();

    // 只发生变化的元信息字段(与原值比较)
    const EDITABLE = [
      "expiry_date", "received_date", "aliquot_date", "remark", "concentration",
      "extinction_coefficient", "serial_no", "asset_no", "responsible_person",
      "project_no", "originator_batch_no", "aliquot_spec",
    ] as const;
    const changes: Record<string, string | number | null> = {};
    const orig = toForm(batch);
    for (const f of EDITABLE) {
      const now = norm(f, (v as Record<string, unknown>)[f]);
      const was = norm(f, (orig as Record<string, unknown>)[f]);
      if (now !== was) changes[f] = now;
    }

    if (Object.keys(changes).length === 0) {
      message.warning("没有任何改动");
      return;
    }

    mut.mutate({
      id: batchId,
      data: {
        ...changes,
        reviewer_username: v.reviewer_username!,
        reviewer_password: v.reviewer_password!,
      },
    });
  };

  return (
    <Modal
      title={batch ? `修改批次信息: ${batch.material_code} / 批号 ${batch.batch_no}` : "修改批次信息"}
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={mut.isPending}
      okText="保存并复核签名"
      width={640}
      destroyOnClose
      afterClose={() => form.resetFields()}
    >
      {isLoading ? (
        <Spin />
      ) : (
        <Form form={form} layout="vertical">
          <Alert
            type="warning" showIcon style={{ marginBottom: 16 }}
            message="批号、数量、位置不可在此修改(数量请走盘点调整,位置请走移库)。"
          />
          <Form.Item name="expiry_date" label="有效期">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="received_date" label="入库日期">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="aliquot_spec" label="分装规格">
            <Input allowClear placeholder="如 100 µL/支" />
          </Form.Item>
          <Form.Item name="originator_batch_no" label="原研药批号">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="concentration" label="浓度">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="extinction_coefficient" label="消光系数">
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="aliquot_date" label="分装日期">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="serial_no" label="序列号">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="asset_no" label="资产编号">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="responsible_person" label="负责人">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="project_no" label="项目编号">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Divider>复核签名(第二位库管员)</Divider>
          <Alert
            type="info" showIcon style={{ marginBottom: 16 }}
            message="修改样品信息需第二位库管员/管理员当场复核确认。请其输入本人工号和密码完成电子签名(不能与修改人相同)。"
          />
          <Form.Item
            name="reviewer_username" label="复核人工号"
            rules={[{ required: true, message: "请输入复核人工号" }]}
          >
            <Input autoComplete="off" placeholder="第二位库管员的工号" />
          </Form.Item>
          <Form.Item
            name="reviewer_password" label="复核人密码"
            rules={[{ required: true, message: "请输入复核人密码" }]}
          >
            <Input.Password autoComplete="new-password" placeholder="第二位库管员的密码" />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
}
