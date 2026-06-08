import { useEffect, useState } from "react";
import { Select, Space, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { listNodes, type StorageNode } from "../../../api/storage";

/**
 * 存放位置三级级联选择器(房间 → 柜/冰箱 → 板层/隔板)。
 * 作为 Form.Item 的受控输入: value = 散放叶子的 location_id; onChange(location_id)。
 * - 选房间 → 加载该房间的柜/冰箱; 选柜/冰箱 → 加载其下 bulk 叶子。
 * - 选到 bulk 叶子(CABINET_LAYER/FRIDGE_SHELF)才解析出 location_id 并回填。
 * - -80 冰箱的下级是冻存架(非 bulk),期1 不在此选择, 提示去专用入库。
 */
interface Props {
  value?: number;                      // location_id
  onChange?: (locationId?: number) => void;
  // 选到 -80℃ 冰箱时上抛该冰箱节点(否则 null), 父级据此切换到冻存选孔
  onFreezerSelect?: (freezer: StorageNode | null) => void;
}

const FRIDGE_COLOR: Record<string, string> = {
  "2-8": "blue",
  "-20": "geekblue",
  "-80": "purple",
  normal: "default",
};

export default function LocationPicker({ value, onChange, onFreezerSelect }: Props) {
  const [roomId, setRoomId] = useState<number>();
  const [midId, setMidId] = useState<number>();   // 柜 / 冰箱
  const [leafId, setLeafId] = useState<number>(); // 板层 / 隔板 节点 id

  // 外部把 value 清空(如 form.resetFields)时, 同步清空内部三级选择
  useEffect(() => {
    if (value === undefined) {
      setRoomId(undefined);
      setMidId(undefined);
      setLeafId(undefined);
    }
  }, [value]);

  const { data: rooms = [] } = useQuery({
    queryKey: ["storage", "nodes", "root"],
    queryFn: () => listNodes().then((r) => r.data),
  });
  const { data: mids = [] } = useQuery({
    queryKey: ["storage", "nodes", roomId],
    queryFn: () => listNodes(roomId).then((r) => r.data),
    enabled: roomId !== undefined,
  });
  const { data: leaves = [] } = useQuery({
    queryKey: ["storage", "nodes", midId],
    queryFn: () => listNodes(midId).then((r) => r.data),
    enabled: midId !== undefined,
  });

  const midNode = mids.find((m) => m.node_id === midId);
  const is80 = midNode?.node_type === "FRIDGE" && midNode?.temp_category === "-80";
  // 期1 只接受 bulk 叶子(有 location_id);-80 的冻存架/孔位不在此选
  const bulkLeaves = leaves.filter((l) => l.capacity_kind === "bulk" && l.location_id != null);

  const label = (n: StorageNode) => n.label || n.code;

  return (
    <Space wrap>
      <Select
        placeholder="房间"
        style={{ width: 130 }}
        value={roomId}
        showSearch
        optionFilterProp="label"
        options={rooms.map((n) => ({ label: label(n), value: n.node_id }))}
        onChange={(v) => {
          setRoomId(v);
          setMidId(undefined);
          setLeafId(undefined);
          onChange?.(undefined);
          onFreezerSelect?.(null);
        }}
      />
      <Select
        placeholder="柜 / 冰箱"
        style={{ width: 180 }}
        value={midId}
        disabled={roomId === undefined}
        showSearch
        optionFilterProp="label"
        options={mids.map((n) => ({
          label: label(n),
          value: n.node_id,
          node: n,
        }))}
        optionRender={(opt) => {
          const n = (opt.data as { node: StorageNode }).node;
          return (
            <Space>
              <span>{label(n)}</span>
              {n.node_type === "FRIDGE" && n.temp_text && (
                <Tag color={FRIDGE_COLOR[n.temp_category ?? "normal"]} style={{ marginInlineEnd: 0 }}>
                  {n.temp_text}
                </Tag>
              )}
            </Space>
          );
        }}
        onChange={(v) => {
          setMidId(v);
          setLeafId(undefined);
          onChange?.(undefined);
          const node = mids.find((m) => m.node_id === v);
          const picked80 = node?.node_type === "FRIDGE" && node?.temp_category === "-80";
          onFreezerSelect?.(picked80 ? node! : null);
        }}
      />
      <Select
        placeholder={is80 ? "↓ 在下方选孔" : "板层 / 隔板"}
        style={{ width: 150 }}
        value={leafId}
        disabled={midId === undefined || is80}
        showSearch
        optionFilterProp="label"
        options={bulkLeaves.map((n) => ({ label: label(n), value: n.node_id, locId: n.location_id }))}
        onChange={(v, opt) => {
          setLeafId(v);
          const locId = (opt as { locId?: number })?.locId;
          onChange?.(locId ?? undefined);
        }}
      />
    </Space>
  );
}
