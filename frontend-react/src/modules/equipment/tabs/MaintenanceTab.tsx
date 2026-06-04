import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table, Tag, Button, Modal, Form, DatePicker, Input, Select, message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import {
  listMaintenances, createMaintenance, MAINTENANCE_TYPE_LABEL,
} from "../../../api/equipment";
import { useAuthStore } from "../../../stores/authStore";

export default function MaintenanceTab({
  equipmentId, canEdit,
}: { equipmentId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["maintenances", equipmentId],
    queryFn: () => listMaintenances(equipmentId).then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createMaintenance(equipmentId, data),
    onSuccess: () => {
      message.success("维护记录已添加");
      setOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ["maintenances", equipmentId] });
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
      maintenance_date: v.maintenance_date.format("YYYY-MM-DD"),
      maintenance_type: v.maintenance_type,
      content: v.content,
      performed_by: v.performed_by,
      next_maintenance_date: v.next_maintenance_date?.format("YYYY-MM-DD") ?? null,
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
          新增维护记录
        </Button>
      )}
      <Table
        rowKey="maintenance_id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "维护日期", dataIndex: "maintenance_date", width: 110 },
          {
            title: "维护类型",
            dataIndex: "maintenance_type",
            width: 100,
            render: (v: string) => MAINTENANCE_TYPE_LABEL[v] ?? v,
          },
          { title: "维护内容", dataIndex: "content", ellipsis: true },
          { title: "执行人", dataIndex: "performed_by", width: 90 },
          {
            title: "下次维护日",
            dataIndex: "next_maintenance_date",
            width: 120,
            render: (v: string | null) => {
              if (!v) return "-";
              const d = dayjs(v).diff(dayjs(), "day");
              return <Tag color={d < 0 ? "red" : d <= 7 ? "red" : d <= 30 ? "gold" : "default"}>{v}</Tag>;
            },
          },
          { title: "备注", dataIndex: "remark", ellipsis: true },
        ]}
      />

      <Modal
        open={open}
        title="新增维护记录"
        onCancel={() => setOpen(false)}
        onOk={handleOk}
        confirmLoading={mutation.isPending}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            maintenance_date: dayjs(),
            maintenance_type: "periodic",
            performed_by: user?.username,
          }}
        >
          <Form.Item name="maintenance_date" label="维护日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="maintenance_type" label="维护类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(MAINTENANCE_TYPE_LABEL).map(([value, label]) => ({
                value, label,
              }))}
            />
          </Form.Item>
          <Form.Item name="content" label="维护内容">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="performed_by" label="执行人" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="next_maintenance_date" label="下次维护日期">
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
