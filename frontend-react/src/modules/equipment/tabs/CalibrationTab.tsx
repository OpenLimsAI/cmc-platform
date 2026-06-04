import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table, Tag, Button, Modal, Form, DatePicker, Input, Select, message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import {
  listCalibrations, createCalibration, CALIBRATION_RESULT_LABEL,
} from "../../../api/equipment";

export default function CalibrationTab({
  equipmentId, canEdit,
}: { equipmentId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["calibrations", equipmentId],
    queryFn: () => listCalibrations(equipmentId).then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createCalibration(equipmentId, data),
    onSuccess: () => {
      message.success("校验记录已添加");
      setOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ["calibrations", equipmentId] });
      queryClient.invalidateQueries({ queryKey: ["equipmentAlerts"] });
    },
    onError: (err: unknown) =>
      message.error(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "添加失败",
      ),
  });

  const handleOk = async () => {
    const v = await form.validateFields();
    mutation.mutate({
      calibration_date: v.calibration_date.format("YYYY-MM-DD"),
      calibration_agency: v.calibration_agency,
      result: v.result,
      certificate_no: v.certificate_no,
      next_calibration_date: v.next_calibration_date?.format("YYYY-MM-DD") ?? null,
      remark: v.remark,
    });
  };

  return (
    <>
      {canEdit && (
        <Button
          type="primary"
          icon={<PlusOutlined />}
          style={{ marginBottom: 12 }}
          onClick={() => setOpen(true)}
        >
          新增校验记录
        </Button>
      )}
      <Table
        rowKey="calibration_id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "校验日期", dataIndex: "calibration_date", width: 110 },
          { title: "校验机构", dataIndex: "calibration_agency", ellipsis: true },
          {
            title: "结论",
            dataIndex: "result",
            width: 90,
            render: (v: string) => {
              const t = CALIBRATION_RESULT_LABEL[v];
              return t ? <Tag color={t.color}>{t.text}</Tag> : v;
            },
          },
          { title: "证书编号", dataIndex: "certificate_no", width: 150 },
          {
            title: "下次校验日",
            dataIndex: "next_calibration_date",
            width: 120,
            render: (v: string | null) => {
              if (!v) return "-";
              const d = dayjs(v).diff(dayjs(), "day");
              return <Tag color={d < 0 ? "red" : d <= 7 ? "red" : d <= 30 ? "gold" : "default"}>{v}</Tag>;
            },
          },
          { title: "备注", dataIndex: "remark", ellipsis: true },
          { title: "录入人", dataIndex: "created_by", width: 90 },
        ]}
      />

      <Modal
        open={open}
        title="新增校验记录"
        onCancel={() => setOpen(false)}
        onOk={handleOk}
        confirmLoading={mutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ calibration_date: dayjs(), result: "qualified" }}>
          <Form.Item name="calibration_date" label="校验日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="calibration_agency" label="校验机构">
            <Input />
          </Form.Item>
          <Form.Item name="result" label="校验结论" rules={[{ required: true }]}>
            <Select
              options={Object.entries(CALIBRATION_RESULT_LABEL).map(([value, v]) => ({
                value, label: v.text,
              }))}
            />
          </Form.Item>
          <Form.Item name="certificate_no" label="证书编号">
            <Input />
          </Form.Item>
          <Form.Item name="next_calibration_date" label="下次校验日期">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
