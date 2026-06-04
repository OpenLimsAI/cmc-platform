import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Descriptions, Tag, Button, Modal, Form, DatePicker, Input, message, Empty,
} from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useState } from "react";
import dayjs from "dayjs";
import { getWarranty, upsertWarranty } from "../../../api/equipment";

export default function WarrantyTab({
  equipmentId, canEdit,
}: { equipmentId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: warranty, isLoading } = useQuery({
    queryKey: ["warranty", equipmentId],
    queryFn: () => getWarranty(equipmentId).then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => upsertWarranty(equipmentId, data),
    onSuccess: () => {
      message.success("保修信息已保存");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["warranty", equipmentId] });
      queryClient.invalidateQueries({ queryKey: ["equipmentAlerts"] });
    },
    onError: (err: unknown) =>
      message.error(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "保存失败",
      ),
  });

  const openEdit = () => {
    if (warranty) {
      form.setFieldsValue({
        ...warranty,
        warranty_start: dayjs(warranty.warranty_start),
        warranty_end: dayjs(warranty.warranty_end),
      });
    } else {
      form.resetFields();
    }
    setOpen(true);
  };

  const handleOk = async () => {
    const v = await form.validateFields();
    mutation.mutate({
      warranty_start: v.warranty_start.format("YYYY-MM-DD"),
      warranty_end: v.warranty_end.format("YYYY-MM-DD"),
      warranty_scope: v.warranty_scope,
      provider_name: v.provider_name,
      provider_contact: v.provider_contact,
      remark: v.remark,
    });
  };

  const daysLeft = warranty ? dayjs(warranty.warranty_end).diff(dayjs(), "day") : null;

  return (
    <>
      {canEdit && (
        <Button
          type="primary"
          icon={<EditOutlined />}
          style={{ marginBottom: 12 }}
          onClick={openEdit}
        >
          {warranty ? "编辑保修信息" : "录入保修信息"}
        </Button>
      )}
      {!isLoading && !warranty && <Empty description="暂无保修信息" />}
      {warranty && (
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="保修起始日">{warranty.warranty_start}</Descriptions.Item>
          <Descriptions.Item label="保修截止日">
            {warranty.warranty_end}{" "}
            {daysLeft !== null && (
              <Tag color={daysLeft < 0 ? "red" : daysLeft <= 30 ? "gold" : "green"}>
                {daysLeft < 0 ? `已过保 ${-daysLeft} 天` : `剩 ${daysLeft} 天`}
              </Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="服务商">{warranty.provider_name ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="联系方式">{warranty.provider_contact ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="保修范围" span={2}>
            {warranty.warranty_scope ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="备注" span={2}>{warranty.remark ?? "-"}</Descriptions.Item>
        </Descriptions>
      )}

      <Modal
        open={open}
        title="保修信息"
        onCancel={() => setOpen(false)}
        onOk={handleOk}
        confirmLoading={mutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="warranty_start" label="保修起始日" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="warranty_end"
            label="保修截止日"
            dependencies={["warranty_start"]}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator: (_, v) =>
                  v && getFieldValue("warranty_start") && v.isBefore(getFieldValue("warranty_start"))
                    ? Promise.reject(new Error("截止日不得早于起始日"))
                    : Promise.resolve(),
              }),
            ]}
          >
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="warranty_scope" label="保修范围">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="provider_name" label="供应商/服务商">
            <Input />
          </Form.Item>
          <Form.Item name="provider_contact" label="联系方式">
            <Input placeholder="电话 / 邮箱" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
