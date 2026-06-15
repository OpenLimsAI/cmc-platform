import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Typography, Table, Input, Select, Space, Tag, Modal, Tooltip,
} from "antd";
import { listAuditLogs, type AuditLogItem } from "../../../api/audit";

const DAY_OPTIONS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
  { value: 365, label: "近 1 年" },
];

// 操作类型 -> 中文标签（审计阅读用，鼠标悬停仍可看到原始 action 键）
const ACTION_LABELS: Record<string, string> = {
  // 认证
  "auth.login": "登录",
  "auth.logout": "登出",
  // 物料
  "material.create": "创建物料",
  "material.update": "更新物料",
  "material.deactivate": "停用物料",
  "material.activate": "启用物料",
  "material.create_from_mdm": "从 MDM 创建物料",
  "material.sync_from_mdm": "从 MDM 同步物料",
  // 批次
  "batch.create": "创建批次",
  // 库存
  "inventory.in": "入库",
  "inventory.out": "出库",
  "inventory.adjust": "库存调整",
  "inventory.transfer": "移库",
  // 入库登记
  "intake.bulk": "批量入库登记",
  // 储位 / 货架
  "storage.occupy": "占用储位",
  "storage.occupy_from": "从原储位占用",
  "storage.release": "释放储位",
  "storage.release_cells": "释放孔位",
  "storage.cabinet.create": "创建存储柜",
  "storage.fridge.create": "创建冰箱",
  "storage.freezer.create": "创建 -80℃ 冰箱",
  "storage.node.add_children": "新增子储位节点",
  "storage.node.update": "更新储位节点",
  "storage.node.delete": "删除储位节点",
  // 库位
  "location.create": "创建库位",
  // 设备
  "equipment.create": "创建设备",
  "equipment.create_from_mdm": "从 MDM 创建设备",
  "equipment.batch_from_mdm": "从 MDM 批量导入设备",
  "equipment.update": "更新设备",
  "equipment.sync_mdm": "从 MDM 同步设备",
  "equipment.deactivate": "停用设备",
  "equipment.calibrate": "设备校准",
  "equipment.maintain": "设备保养",
  "equipment.repair": "设备报修",
  "equipment.repair_complete": "维修完成",
  "equipment.attachment_upload": "上传附件",
  "equipment.attachment_delete": "删除附件",
};

// 对象类型 -> 中文标签
const ENTITY_LABELS: Record<string, string> = {
  material: "物料",
  batch: "批次",
  inventory_txn: "库存流水",
  user: "用户",
  location: "库位",
  equipment: "设备",
  storage_node: "储位节点",
};

const actionLabel = (a: string) => ACTION_LABELS[a] ?? a;

// 按业务域给操作标签上色，便于快速扫读
const actionColor = (a: string) => {
  const domain = a.split(".")[0];
  return (
    {
      auth: "blue",
      material: "geekblue",
      batch: "geekblue",
      inventory: "green",
      intake: "gold",
      storage: "cyan",
      location: "cyan",
      equipment: "purple",
    } as Record<string, string>
  )[domain];
};

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
          style={{ width: 240 }}
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
            render: (v: string) => (
              <Tooltip title={v}>
                <Tag color={actionColor(v)}>{actionLabel(v)}</Tag>
              </Tooltip>
            ),
          },
          {
            title: "对象类型",
            dataIndex: "entity_type",
            width: 120,
            render: (v: string | null) => (v ? ENTITY_LABELS[v] ?? v : "—"),
          },
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
              <b>操作:</b> {actionLabel(detail.action)}
              <Typography.Text type="secondary">（{detail.action}）</Typography.Text>
              &nbsp; <b>用户:</b> {detail.username ?? "-"} &nbsp;
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
