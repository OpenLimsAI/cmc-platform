import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table, Tag, Button, Modal, Form, DatePicker, Input, Select, InputNumber, message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import {
  listRepairs, createRepair, completeRepair, REPAIR_TYPE_LABEL, type Repair,
} from "../../../api/equipment";
import { getErrorDetail } from "../../../shared/errors";

export default function RepairTab({
  equipmentId, canEdit,
}: { equipmentId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [completing, setCompleting] = useState<Repair | null>(null);
  const [form] = Form.useForm();
  const [completeForm] = Form.useForm();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["repairs", equipmentId] });
    queryClient.invalidateQueries({ queryKey: ["equipment"] });
    queryClient.invalidateQueries({ queryKey: ["equipmentDetail", equipmentId] });
  };

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["repairs", equipmentId],
    queryFn: () => listRepairs(equipmentId).then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createRepair(equipmentId, data),
    onSuccess: () => {
      message.success("维修记录已登记(设备已标记为送修中)");
      setOpen(false);
      form.resetFields();
      invalidate();
    },
    onError: (err: unknown) =>
      message.error(
        getErrorDetail(err, "登记失败"),
      ),
  });

  const completeMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      completeRepair(equipmentId, completing!.repair_id, data),
    onSuccess: () => {
      message.success("维修完成已登记");
      setCompleting(null);
      completeForm.resetFields();
      invalidate();
    },
    onError: (err: unknown) =>
      message.error(
        getErrorDetail(err, "登记失败"),
      ),
  });

  const handleCreate = async () => {
    const v = await form.validateFields();
    createMutation.mutate({
      report_date: v.report_date.format("YYYY-MM-DD"),
      fault_description: v.fault_description,
      repair_type: v.repair_type,
      repair_provider: v.repair_provider,
      remark: v.remark,
    });
  };

  const handleComplete = async () => {
    const v = await completeForm.validateFields();
    completeMutation.mutate({
      completion_date: v.completion_date.format("YYYY-MM-DD"),
      repair_cost: v.repair_cost,
      conclusion: v.conclusion,
    });
  };

  return (
    <>
      {canEdit && (
        <Button
          type="primary"
          icon={<PlusOutlined />}
          style={{ marginBottom: 12 }}
          onClick={() => { form.resetFields(); setOpen(true); }}
        >
          登记报修
        </Button>
      )}
      <Table
        rowKey="repair_id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "报修日期", dataIndex: "report_date", width: 110 },
          { title: "故障描述", dataIndex: "fault_description", ellipsis: true },
          {
            title: "维修类型",
            dataIndex: "repair_type",
            width: 100,
            render: (v: string) => REPAIR_TYPE_LABEL[v] ?? v,
          },
          { title: "维修单位", dataIndex: "repair_provider", width: 140, ellipsis: true },
          {
            title: "状态",
            key: "state",
            width: 90,
            render: (_: unknown, r: Repair) =>
              r.completion_date
                ? <Tag color="green">已完成</Tag>
                : <Tag color="orange">维修中</Tag>,
          },
          { title: "完成日期", dataIndex: "completion_date", width: 110, render: (v) => v ?? "-" },
          {
            title: "费用(元)",
            dataIndex: "repair_cost",
            width: 100,
            render: (v: number | null) => v ?? "-",
          },
          { title: "维修结论", dataIndex: "conclusion", ellipsis: true },
          ...(canEdit
            ? [{
                title: "操作",
                key: "actions",
                width: 100,
                render: (_: unknown, r: Repair) =>
                  r.completion_date ? null : (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => {
                        setCompleting(r);
                        // 先重置:上次"取消"关闭时填的费用/结论会残留,不清会串写到这条维修单
                        completeForm.resetFields();
                        completeForm.setFieldsValue({ completion_date: dayjs() });
                      }}
                    >
                      完成登记
                    </Button>
                  ),
              }]
            : []),
        ]}
      />

      <Modal
        open={open}
        title="登记报修(设备将自动标记为送修中)"
        onCancel={() => setOpen(false)}
        onOk={handleCreate}
        confirmLoading={createMutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ report_date: dayjs(), repair_type: "external" }}>
          <Form.Item name="report_date" label="报修日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="fault_description" label="故障描述" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="repair_type" label="维修类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(REPAIR_TYPE_LABEL).map(([value, label]) => ({
                value, label,
              }))}
            />
          </Form.Item>
          <Form.Item name="repair_provider" label="维修单位">
            <Input placeholder="内部维修组 / 外部服务商名称" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!completing}
        title="维修完成登记"
        onCancel={() => setCompleting(null)}
        onOk={handleComplete}
        confirmLoading={completeMutation.isPending}
        destroyOnClose
      >
        <Form form={completeForm} layout="vertical">
          <Form.Item name="completion_date" label="完成日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="repair_cost" label="维修费用(元)">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="conclusion" label="维修结论">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
