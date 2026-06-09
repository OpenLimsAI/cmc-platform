import { useEffect, useState } from "react";
import {
  Card, Tree, Button, Space, Modal, Form, Input, InputNumber, Select,
  Tag, message, Typography, Descriptions, Empty, Alert,
} from "antd";
import {
  PlusOutlined, InboxOutlined, EditOutlined, DeleteOutlined, ExperimentOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";
import type { DataNode } from "antd/es/tree";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listNodes, createCabinet, createFridge, createFreezer, updateNode, deleteNode,
  listCells, releaseCell, addChildren,
  type StorageNode, type CabinetCreate, type FridgeCreate, type FreezerCreate,
  type Cell, type AddChildrenRequest,
} from "../../../api/storage";
import CellGrid from "../components/CellGrid";
import { useAuthStore } from "../../../stores/authStore";
import { getErrorDetail } from "../../../shared/errors";

type TNode = DataNode & { raw: StorageNode };
type ChildField = "count" | "storage_condition" | "layers_per_rack" | "boxes_per_layer" | "cells_per_box";

// 选中节点可追加的下级类型 + 该表单需要的字段(支持异构/分批)
function getAddSpec(n: StorageNode):
  { childType: AddChildrenRequest["child_type"]; childLabel: string; fields: ChildField[] } | null {
  switch (n.node_type) {
    case "CABINET": return { childType: "CABINET_LAYER", childLabel: "板层", fields: ["count", "storage_condition"] };
    case "FRIDGE": return n.temp_category === "-80"
      ? { childType: "RACK", childLabel: "冻存架", fields: ["count", "layers_per_rack", "boxes_per_layer", "cells_per_box"] }
      : { childType: "FRIDGE_SHELF", childLabel: "隔板", fields: ["count"] };
    case "RACK": return { childType: "RACK_LAYER", childLabel: "层", fields: ["count", "boxes_per_layer", "cells_per_box"] };
    case "RACK_LAYER": return { childType: "BOX", childLabel: "盒区", fields: ["count", "cells_per_box"] };
    case "BOX": return { childType: "CELL", childLabel: "孔", fields: ["count"] };
    default: return null;
  }
}

const TYPE_LABEL: Record<string, string> = {
  ROOM: "房间", CABINET: "试剂柜", CABINET_LAYER: "板层",
  FRIDGE: "冰箱", FRIDGE_SHELF: "隔板",
  RACK: "冻存架", RACK_LAYER: "层", BOX: "盒区", CELL: "孔",
};
const FRIDGE_COLOR: Record<string, string> = {
  "2-8": "blue", "-20": "geekblue", "-80": "purple", normal: "default",
};

function toTNode(n: StorageNode): TNode {
  return {
    key: n.node_id,
    isLeaf: !n.has_children,
    raw: n,
    title: (
      <Space size={4}>
        <span style={{ textDecoration: n.is_active ? "none" : "line-through", opacity: n.is_active ? 1 : 0.5 }}>
          {n.label || n.code}
        </span>
        {n.node_type === "FRIDGE" && n.temp_text && (
          <Tag color={FRIDGE_COLOR[n.temp_category ?? "normal"]} style={{ marginInlineEnd: 0 }}>
            {n.temp_text}
          </Tag>
        )}
        {!n.is_active && <Tag color="default" style={{ marginInlineEnd: 0 }}>已停用</Tag>}
      </Space>
    ),
  };
}

// 递归把某 key 节点的 children 替换 / 移除 / 更新自身
function setChildren(list: TNode[], key: number, children: TNode[]): TNode[] {
  return list.map((n) =>
    n.key === key ? { ...n, children }
      : n.children ? { ...n, children: setChildren(n.children as TNode[], key, children) } : n);
}
function replaceNode(list: TNode[], key: number, raw: StorageNode): TNode[] {
  return list.map((n) => {
    if (n.key === key) return { ...toTNode(raw), children: n.children };
    return n.children ? { ...n, children: replaceNode(n.children as TNode[], key, raw) } : n;
  });
}
function removeNode(list: TNode[], key: number): TNode[] {
  return list.filter((n) => n.key !== key)
    .map((n) => (n.children ? { ...n, children: removeNode(n.children as TNode[], key) } : n));
}

export default function StoragePage() {
  const [treeData, setTreeData] = useState<TNode[]>([]);
  const [expanded, setExpanded] = useState<number[]>([]);
  const [selected, setSelected] = useState<StorageNode | null>(null);
  const [cabOpen, setCabOpen] = useState(false);
  const [fridgeOpen, setFridgeOpen] = useState(false);
  const [freezerOpen, setFreezerOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [delOpen, setDelOpen] = useState(false);
  const [delText, setDelText] = useState("");
  const [cabForm] = Form.useForm();
  const [fridgeForm] = Form.useForm();
  const [freezerForm] = Form.useForm();
  const [renameForm] = Form.useForm();
  const [addForm] = Form.useForm();
  const qc = useQueryClient();
  // 删除仅管理员;编辑/新增下级给库管员(页面本身已 warehouse 限入)
  const isAdmin = useAuthStore((s) => s.hasRole("SYS_ADMIN"));
  const addSpec = selected ? getAddSpec(selected) : null;
  // -80 模板规模实时预览
  const fzWatch = Form.useWatch([], freezerForm);
  const fzTotal =
    (fzWatch?.rack_count ?? 0) * (fzWatch?.layers_per_rack ?? 0) *
    (fzWatch?.boxes_per_layer ?? 0) * (fzWatch?.cells_per_box ?? 0);

  const reloadRoot = async () => {
    const rooms = await listNodes().then((r) => r.data);
    setTreeData(rooms.map(toTNode));
    setExpanded([]);
    setSelected(null);
  };
  useEffect(() => { reloadRoot(); }, []);

  const onLoadData = async (node: { key: React.Key }) => {
    const kids = await listNodes(Number(node.key)).then((r) => r.data);
    setTreeData((cur) => setChildren(cur, Number(node.key), kids.map(toTNode)));
  };

  // 追加下级后局部刷新该节点子树并展开,不丢失其他展开状态
  const refreshChildren = async (parentId: number) => {
    const kids = await listNodes(parentId).then((r) => r.data);
    setTreeData((cur) => setChildren(cur, parentId, kids.map(toTNode)));
    setExpanded((e) => (e.includes(parentId) ? e : [...e, parentId]));
  };

  const cabMutation = useMutation({
    mutationFn: (data: CabinetCreate) => createCabinet(data),
    onSuccess: async () => {
      message.success("试剂柜已创建");
      setCabOpen(false); cabForm.resetFields();
      await reloadRoot();
    },
    onError: (e) => message.error(getErrorDetail(e, "创建失败")),
  });
  const fridgeMutation = useMutation({
    mutationFn: (data: FridgeCreate) => createFridge(data),
    onSuccess: async () => {
      message.success("冰箱已创建");
      setFridgeOpen(false); fridgeForm.resetFields();
      await reloadRoot();
    },
    onError: (e) => message.error(getErrorDetail(e, "创建失败")),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, label, is_active }: { id: number; label?: string; is_active?: boolean }) =>
      updateNode(id, { label, is_active }),
    onSuccess: (res) => {
      const raw = res.data;
      setTreeData((cur) => replaceNode(cur, raw.node_id, raw));
      setSelected(raw);
      setRenameOpen(false);
      message.success("已更新");
    },
    onError: (e) => message.error(getErrorDetail(e, "更新失败")),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNode(id),
    onSuccess: (_res, id) => {
      setTreeData((cur) => removeNode(cur, id));
      setSelected(null);
      setDelOpen(false);
      setDelText("");
      message.success("已删除");
    },
    onError: (e) => message.error(getErrorDetail(e, "删除失败,可能该位置下仍有库存")),
  });
  const freezerMutation = useMutation({
    mutationFn: (data: FreezerCreate) => createFreezer(data),
    onSuccess: async () => {
      message.success("-80℃ 冰箱已创建");
      setFreezerOpen(false); freezerForm.resetFields();
      await reloadRoot();
    },
    onError: (e) => message.error(getErrorDetail(e, "创建失败")),
  });
  const addMutation = useMutation({
    mutationFn: ({ parentId, data }: { parentId: number; data: AddChildrenRequest }) =>
      addChildren(parentId, data),
    onSuccess: async (res, vars) => {
      message.success(`已新增 ${res.data.created} 个(${res.data.codes.join("、")})`);
      setAddOpen(false); addForm.resetFields();
      await refreshChildren(vars.parentId);
    },
    onError: (e) => message.error(getErrorDetail(e, "新增失败")),
  });

  // 选中盒区 → 加载孔位热力图
  const isBox = selected?.node_type === "BOX";
  const { data: boxCells = [] } = useQuery({
    queryKey: ["box-cells", selected?.node_id],
    queryFn: () => listCells(selected!.node_id).then((r) => r.data),
    enabled: isBox,
  });
  const releaseMutation = useMutation({
    mutationFn: (cellId: number) => releaseCell(cellId),
    onSuccess: () => {
      message.success("已释放该孔");
      qc.invalidateQueries({ queryKey: ["box-cells", selected?.node_id] });
    },
    onError: (e) => message.error(getErrorDetail(e, "释放失败")),
  });

  const onCellClick = (cell: Cell) => {
    if (!cell.occupied) return;
    Modal.confirm({
      title: "释放该孔?",
      content: `${cell.material_code ?? ""} ${cell.material_name ?? ""} 批号 ${cell.batch_no ?? ""}${cell.sample_label ? ` / 样品 ${cell.sample_label}` : ""}`,
      okText: "释放(取出)",
      okButtonProps: { danger: true },
      onOk: () => releaseMutation.mutate(cell.cell_node_id),
    });
  };

  return (
    <>
      <Typography.Title level={4}>位置管理</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCabOpen(true)}>
          新增试剂柜
        </Button>
        <Button icon={<InboxOutlined />} onClick={() => setFridgeOpen(true)}>
          新增普通冰箱
        </Button>
        <Button icon={<ExperimentOutlined />} onClick={() => setFreezerOpen(true)}>
          新增 -80℃ 冰箱
        </Button>
      </Space>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <Card title="位置树" style={{ flex: 1, minWidth: 360 }} size="small">
          {treeData.length === 0 ? (
            <Empty description="暂无位置,请新增试剂柜或冰箱" />
          ) : (
            <Tree
              treeData={treeData}
              loadData={onLoadData}
              expandedKeys={expanded}
              onExpand={(keys) => setExpanded(keys.map(Number))}
              selectedKeys={selected ? [selected.node_id] : []}
              onSelect={(_keys, info) => setSelected((info.node as TNode).raw)}
              showLine
            />
          )}
        </Card>

        <Card title="节点详情" style={{ flex: 1, minWidth: 320 }} size="small">
          {!selected ? (
            <Empty description="在左侧选择一个节点" />
          ) : (
            <>
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="类型">{TYPE_LABEL[selected.node_type] ?? selected.node_type}</Descriptions.Item>
                <Descriptions.Item label="名称">{selected.label || selected.code}</Descriptions.Item>
                <Descriptions.Item label="路径">{selected.path}</Descriptions.Item>
                {selected.temp_text && (
                  <Descriptions.Item label="温区">{selected.temp_text}</Descriptions.Item>
                )}
                <Descriptions.Item label="状态">
                  {selected.is_active ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>}
                </Descriptions.Item>
                {selected.capacity_kind && (
                  <Descriptions.Item label="存储">
                    {selected.capacity_kind === "bulk" ? "散放(批次+数量)" : "单孔(单占用)"}
                  </Descriptions.Item>
                )}
              </Descriptions>
              <Space style={{ marginTop: 16 }} wrap>
                <Button
                  icon={<EditOutlined />}
                  onClick={() => {
                    renameForm.setFieldsValue({ label: selected.label || selected.code });
                    setRenameOpen(true);
                  }}
                >
                  改名
                </Button>
                <Button
                  loading={updateMutation.isPending}
                  onClick={() => updateMutation.mutate({ id: selected.node_id, is_active: !selected.is_active })}
                >
                  {selected.is_active ? "停用" : "启用"}
                </Button>
                {addSpec && (
                  <Button
                    icon={<ApartmentOutlined />}
                    onClick={() => { addForm.resetFields(); setAddOpen(true); }}
                  >
                    新增{addSpec.childLabel}
                  </Button>
                )}
                {isAdmin ? (
                  <Button danger icon={<DeleteOutlined />} onClick={() => { setDelText(""); setDelOpen(true); }}>
                    删除
                  </Button>
                ) : (
                  <Typography.Text type="secondary">删除需管理员</Typography.Text>
                )}
              </Space>

              {isBox && (
                <div style={{ marginTop: 20 }}>
                  <Typography.Text strong>孔位占用</Typography.Text>
                  <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                    灰=空闲 · 绿=已占用(在效期) · 红=已过期 · 点击占用孔可释放
                  </Typography.Text>
                  <div style={{ marginTop: 10 }}>
                    {boxCells.length === 0 ? (
                      <Empty description="该盒无孔位" />
                    ) : (
                      <CellGrid cells={boxCells} onCellClick={onCellClick} />
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {/* 新增试剂柜 */}
      <Modal
        title="新增试剂柜"
        open={cabOpen}
        onCancel={() => setCabOpen(false)}
        onOk={() => cabForm.submit()}
        confirmLoading={cabMutation.isPending}
        okText="创建"
      >
        <Form form={cabForm} layout="vertical" onFinish={(v) => cabMutation.mutate(v)}>
          <Form.Item name="room_no" label="房间号" rules={[{ required: true }]}>
            <Input placeholder="如 2251(已存在则复用)" />
          </Form.Item>
          <Form.Item name="cabinet_no" label="柜号" rules={[{ required: true }]}>
            <Input placeholder="如 C08" />
          </Form.Item>
          <Form.Item name="layer_count" label="板层数" rules={[{ required: true }]} initialValue={5}>
            <InputNumber min={1} max={60} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="storage_condition" label="存储条件">
            <Input placeholder="如 常温 / 避光" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新增普通冰箱 */}
      <Modal
        title="新增普通冰箱"
        open={fridgeOpen}
        onCancel={() => setFridgeOpen(false)}
        onOk={() => fridgeForm.submit()}
        confirmLoading={fridgeMutation.isPending}
        okText="创建"
      >
        <Form form={fridgeForm} layout="vertical" onFinish={(v) => fridgeMutation.mutate(v)}>
          <Form.Item name="room_no" label="房间号" rules={[{ required: true }]}>
            <Input placeholder="如 2251" />
          </Form.Item>
          <Form.Item name="fridge_name" label="冰箱名/编号" rules={[{ required: true }]}>
            <Input placeholder="如 RF-01" maxLength={20} />
          </Form.Item>
          <Form.Item name="temp_category" label="温区" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "2-8", label: "2~8℃" },
                { value: "-20", label: "-20~-40℃" },
                { value: "normal", label: "常温" },
              ]}
            />
          </Form.Item>
          <Form.Item name="shelf_count" label="隔板数" rules={[{ required: true }]} initialValue={4}>
            <InputNumber min={1} max={60} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新增 -80℃ 冰箱 */}
      <Modal
        title="新增 -80℃ 冰箱"
        open={freezerOpen}
        onCancel={() => setFreezerOpen(false)}
        onOk={() => freezerForm.submit()}
        confirmLoading={freezerMutation.isPending}
        okText="创建"
        width={560}
      >
        <Form form={freezerForm} layout="vertical" onFinish={(v) => freezerMutation.mutate(v)}>
          <Form.Item name="room_no" label="房间号" rules={[{ required: true }]}>
            <Input placeholder="如 2251" />
          </Form.Item>
          <Form.Item name="fridge_name" label="冰箱名/编号" rules={[{ required: true }]}>
            <Input placeholder="如 TT3" maxLength={20} />
          </Form.Item>
          <Space size="large" wrap>
            <Form.Item name="rack_count" label="冻存架数(A~)" rules={[{ required: true }]} initialValue={16}>
              <InputNumber min={1} max={26} />
            </Form.Item>
            <Form.Item name="layers_per_rack" label="每架层数" rules={[{ required: true }]} initialValue={5}>
              <InputNumber min={1} max={20} />
            </Form.Item>
            <Form.Item name="boxes_per_layer" label="每层盒区(A~)" rules={[{ required: true }]} initialValue={4}>
              <InputNumber min={1} max={26} />
            </Form.Item>
            <Form.Item name="cells_per_box" label="每盒孔数" rules={[{ required: true }]} initialValue={100}>
              <InputNumber min={1} max={400} />
            </Form.Item>
          </Space>
          <Alert
            type={fzTotal > 60000 ? "error" : "info"}
            showIcon
            message={
              fzTotal > 60000
                ? `将生成 ${fzTotal} 个孔位,超过 60000 上限,请减少规模`
                : `将一次性生成 ${fzTotal || 0} 个孔位(架×层×盒×孔)`
            }
          />
          <Form.Item name="remark" label="备注" style={{ marginTop: 12 }}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 改名 */}
      <Modal
        title="重命名"
        open={renameOpen}
        onCancel={() => setRenameOpen(false)}
        onOk={() => renameForm.submit()}
        confirmLoading={updateMutation.isPending}
        okText="保存"
      >
        <Form
          form={renameForm}
          layout="vertical"
          onFinish={(v) => selected && updateMutation.mutate({ id: selected.node_id, label: v.label })}
        >
          <Form.Item name="label" label="名称" rules={[{ required: true, max: 80 }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新增下级(按节点类型动态字段;支持异构/分批) */}
      <Modal
        title={addSpec && selected ? `在「${selected.label || selected.code}」下新增${addSpec.childLabel}` : "新增下级"}
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={() => addForm.submit()}
        confirmLoading={addMutation.isPending}
        okText="新增"
      >
        {addSpec && selected && (
          <Form
            form={addForm}
            layout="vertical"
            initialValues={{ count: 1, layers_per_rack: 5, boxes_per_layer: 4, cells_per_box: 100 }}
            onFinish={(v) => addMutation.mutate({
              parentId: selected.node_id,
              data: { child_type: addSpec.childType, ...v },
            })}
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`编号在现有 ${addSpec.childLabel} 之后自动续接;可对不同${TYPE_LABEL[selected.node_type] ?? "节点"}设置不同规格,实现异构。`}
            />
            <Form.Item name="count" label={`新增${addSpec.childLabel}数量`} rules={[{ required: true }]}>
              <InputNumber min={1} max={1000} style={{ width: "100%" }} />
            </Form.Item>
            {addSpec.fields.includes("layers_per_rack") && (
              <Form.Item name="layers_per_rack" label="每架层数" rules={[{ required: true }]}>
                <InputNumber min={1} max={20} style={{ width: "100%" }} />
              </Form.Item>
            )}
            {addSpec.fields.includes("boxes_per_layer") && (
              <Form.Item name="boxes_per_layer" label="每层盒区数(A~)" rules={[{ required: true }]}>
                <InputNumber min={1} max={26} style={{ width: "100%" }} />
              </Form.Item>
            )}
            {addSpec.fields.includes("cells_per_box") && (
              <Form.Item name="cells_per_box" label="每盒孔数" rules={[{ required: true }]} extra="常见:81(9×9) / 100(10×10)">
                <InputNumber min={1} max={400} style={{ width: "100%" }} />
              </Form.Item>
            )}
            {addSpec.fields.includes("storage_condition") && (
              <Form.Item name="storage_condition" label="存储条件">
                <Input placeholder="如 常温 / 避光" />
              </Form.Item>
            )}
          </Form>
        )}
      </Modal>

      {/* 删除二次确认:仅管理员,需输入节点名 */}
      <Modal
        title="删除节点(不可恢复)"
        open={delOpen}
        onCancel={() => setDelOpen(false)}
        onOk={() => selected && deleteMutation.mutate(selected.node_id)}
        okText="确认删除"
        okButtonProps={{
          danger: true,
          disabled: !selected || delText.trim() !== (selected.label || selected.code),
          loading: deleteMutation.isPending,
        }}
      >
        {selected && (
          <>
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 12 }}
              message="将删除该节点及其全部下级"
              description={<>路径:{selected.path}<br />若其下存在批次 / 库存(含 -80 占用)将被拒绝。</>}
            />
            <Typography.Paragraph style={{ marginBottom: 8 }}>
              请输入该节点名称 <b>{selected.label || selected.code}</b> 以确认:
            </Typography.Paragraph>
            <Input
              value={delText}
              onChange={(e) => setDelText(e.target.value)}
              placeholder={selected.label || selected.code}
              onPressEnter={() => {
                if (delText.trim() === (selected.label || selected.code)) deleteMutation.mutate(selected.node_id);
              }}
            />
          </>
        )}
      </Modal>
    </>
  );
}
