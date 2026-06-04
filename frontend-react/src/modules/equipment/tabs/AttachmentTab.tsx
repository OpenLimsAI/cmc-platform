import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table, Tag, Button, Modal, Form, Input, Select, Upload, message, Popconfirm,
} from "antd";
import { UploadOutlined, DownloadOutlined, DeleteOutlined } from "@ant-design/icons";
import {
  listAttachments, uploadAttachment, downloadAttachment, deleteAttachment,
  ATTACHMENT_TAG_LABEL, type Attachment,
} from "../../../api/equipment";

function fmtSize(bytes: number | null): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function AttachmentTab({
  equipmentId, canEdit,
}: { equipmentId: number; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [form] = Form.useForm();

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["attachments", equipmentId] });

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["attachments", equipmentId],
    queryFn: () => listAttachments(equipmentId).then((r) => r.data),
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      const v = form.getFieldsValue();
      return uploadAttachment(equipmentId, file!, v.tag, v.description);
    },
    onSuccess: () => {
      message.success("附件已上传");
      setOpen(false);
      setFile(null);
      form.resetFields();
      invalidate();
    },
    onError: (err: unknown) =>
      message.error(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "上传失败",
      ),
  });

  const deleteMutation = useMutation({
    mutationFn: (attachmentId: number) => deleteAttachment(equipmentId, attachmentId),
    onSuccess: () => {
      message.success("附件已删除");
      invalidate();
    },
    onError: (err: unknown) =>
      message.error(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "删除失败",
      ),
  });

  return (
    <>
      {canEdit && (
        <Button
          type="primary"
          icon={<UploadOutlined />}
          style={{ marginBottom: 12 }}
          onClick={() => setOpen(true)}
        >
          上传附件
        </Button>
      )}
      <Table
        rowKey="attachment_id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "文件名", dataIndex: "file_name", ellipsis: true },
          {
            title: "标签",
            dataIndex: "tag",
            width: 90,
            render: (v: string | null) => (v ? <Tag>{ATTACHMENT_TAG_LABEL[v] ?? v}</Tag> : "-"),
          },
          { title: "说明", dataIndex: "description", ellipsis: true },
          {
            title: "大小",
            dataIndex: "file_size",
            width: 90,
            render: (v: number | null) => fmtSize(v),
          },
          { title: "上传时间", dataIndex: "uploaded_at", width: 170 },
          { title: "上传人", dataIndex: "uploaded_by", width: 90 },
          {
            title: "操作",
            key: "actions",
            width: 130,
            render: (_: unknown, r: Attachment) => (
              <>
                <Button
                  type="link"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => downloadAttachment(equipmentId, r.attachment_id, r.file_name)}
                >
                  下载
                </Button>
                {canEdit && (
                  <Popconfirm
                    title="确认删除该附件？"
                    onConfirm={() => deleteMutation.mutate(r.attachment_id)}
                  >
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                )}
              </>
            ),
          },
        ]}
      />

      <Modal
        open={open}
        title="上传附件"
        onCancel={() => { setOpen(false); setFile(null); }}
        onOk={() => {
          if (!file) {
            message.warning("请先选择文件");
            return;
          }
          uploadMutation.mutate();
        }}
        confirmLoading={uploadMutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item label="文件(≤50MB)" required>
            <Upload
              maxCount={1}
              beforeUpload={(f) => {
                setFile(f);
                return false;
              }}
              onRemove={() => setFile(null)}
              fileList={file ? [{ uid: "-1", name: file.name }] : []}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item name="tag" label="分类标签">
            <Select
              allowClear
              options={Object.entries(ATTACHMENT_TAG_LABEL).map(([value, label]) => ({
                value, label,
              }))}
            />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input maxLength={200} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
