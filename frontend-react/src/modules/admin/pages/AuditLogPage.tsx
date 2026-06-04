import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Typography, Table, Input, Select, Space, Tag, Modal,
} from "antd";
import { listAuditLogs, type AuditLogItem } from "../../../api/audit";

const DAY_OPTIONS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
  { value: 365, label: "近 1 年" },
];

export default function AuditLogPage() {
  const [username, setUsername] = useState("");
  const [action, setAction] = useState("");
  const [days, setDays] = useState(30);
  const [detail, setDetail] = useState<AuditLogItem | null>(null);

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["auditLogs", username, action, days],
    queryFn: () =>
      listAuditLogs({
        username: username || undefined,
        action: action || undefined,
        days,
        limit: 500,
      }).then((r) => r.data),
  });

  return (
    <>
      <Typography.Title level={4}>审计日志</Typography.Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder="操作用户"
          style={{ width: 180 }}
          allowClear
          onSearch={setUsername}
        />
        <Input.Search
          placeholder="操作类型(如 inventory.out)"
          style={{ width: 220 }}
          allowClear
          onSearch={setAction}
        />
        <Select value={days} onChange={setDays} options={DAY_OPTIONS} style={{ width: 120 }} />
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={isLoading}
        dataSource={logs}
        pagination={{ pageSize: 50 }}
        onRow={(r) => ({ onClick: () => setDetail(r), style: { cursor: "pointer" } })}
        columns={[
          { title: "ID", dataIndex: "id", width: 80 },
          { title: "时间", dataIndex: "created_at", width: 170 },
          { title: "用户", dataIndex: "username", width: 110 },
          {
            title: "操作",
            dataIndex: "action",
            width: 180,
            render: (v: string) => <Tag>{v}</Tag>,
          },
          { title: "对象类型", dataIndex: "entity_type", width: 120 },
          { title: "对象ID", dataIndex: "entity_id", width: 90 },
          { title: "来源IP", dataIndex: "source_ip", width: 130 },
        ]}
      />
      <Modal
        open={!!detail}
        title={`审计详情 #${detail?.id ?? ""}`}
        footer={null}
        width={720}
        onCancel={() => setDetail(null)}
      >
        {detail && (
          <>
            <Typography.Paragraph>
              <b>操作:</b> {detail.action} &nbsp; <b>用户:</b> {detail.username ?? "-"} &nbsp;
              <b>时间:</b> {detail.created_at}
            </Typography.Paragraph>
            <Typography.Title level={5}>操作前</Typography.Title>
            <pre style={{ maxHeight: 200, overflow: "auto", background: "#fafafa", padding: 8 }}>
              {detail.before_json ? JSON.stringify(detail.before_json, null, 2) : "—"}
            </pre>
            <Typography.Title level={5}>操作后</Typography.Title>
            <pre style={{ maxHeight: 200, overflow: "auto", background: "#fafafa", padding: 8 }}>
              {detail.after_json ? JSON.stringify(detail.after_json, null, 2) : "—"}
            </pre>
          </>
        )}
      </Modal>
    </>
  );
}
