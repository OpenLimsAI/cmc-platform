import { useMemo, useState } from "react";
import { Select, Space, Segmented, InputNumber, Button, Tag, Alert, message } from "antd";
import { useQuery } from "@tanstack/react-query";
import {
  listNodes, listCells, findFreeCells, type StorageNode,
} from "../../../api/storage";
import CellGrid from "../../storage/components/CellGrid";

/** -80℃ 选孔结果(上抛给入库页,决定走 occupy 还是 occupy-from)。 */
export type FreezerSelection =
  | { mode: "auto" | "manual"; cellIds: number[]; addresses: string[] }
  | { mode: "from"; startCellId?: number; startAddr?: string; count: number };

interface Props {
  freezer: StorageNode;
  onChange?: (sel: FreezerSelection) => void;
  // 注:切冰箱 / 入库成功后的整体重置由父组件用 key 触发重新挂载实现(避免 effect 内 setState)。
}

/**
 * -80℃ 冻存选孔,三种取位方式:
 *   自动分配 — 输入 N,系统取下一组 N 个空孔;
 *   起始填充 — 选起始孔 + N,从起始孔起连续 N 个(后端校验须全空);
 *   手动选孔 — 架→层→盒级联 + 热力图点选。
 */
export default function FreezerCellPicker({ freezer, onChange }: Props) {
  const [mode, setMode] = useState<"auto" | "from" | "manual">("auto");
  const [autoN, setAutoN] = useState(1);
  const [fromN, setFromN] = useState(1);
  const [startCell, setStartCell] = useState<{ id: number; addr: string }>();
  const [picked, setPicked] = useState<Map<number, string>>(new Map());
  const [rackId, setRackId] = useState<number>();
  const [layerId, setLayerId] = useState<number>();
  const [boxId, setBoxId] = useState<number>();

  const clearAll = () => {
    setStartCell(undefined); setPicked(new Map());
    setRackId(undefined); setLayerId(undefined); setBoxId(undefined);
  };

  // 切换取位方式:清空已选并上抛空(原先放在 effect 里,改为事件回调,避免 effect 内同步 setState)
  const changeMode = (m: typeof mode) => {
    setMode(m);
    clearAll();
    if (m === "auto") onChange?.({ mode: "auto", cellIds: [], addresses: [] });
    if (m === "manual") onChange?.({ mode: "manual", cellIds: [], addresses: [] });
    if (m === "from") onChange?.({ mode: "from", count: fromN });
  };

  const { data: racks = [] } = useQuery({
    queryKey: ["fz", freezer.node_id, "racks"],
    queryFn: () => listNodes(freezer.node_id).then((r) => r.data),
  });
  const { data: layers = [] } = useQuery({
    queryKey: ["fz", "layers", rackId],
    queryFn: () => listNodes(rackId).then((r) => r.data),
    enabled: rackId !== undefined,
  });
  const { data: boxes = [] } = useQuery({
    queryKey: ["fz", "boxes", layerId],
    queryFn: () => listNodes(layerId).then((r) => r.data),
    enabled: layerId !== undefined,
  });
  const { data: cells = [] } = useQuery({
    queryKey: ["fz", "cells", boxId, picked.size, startCell?.id],
    queryFn: () => listCells(boxId!).then((r) => r.data),
    enabled: boxId !== undefined,
  });

  const rack = racks.find((r) => r.node_id === rackId);
  const layer = layers.find((l) => l.node_id === layerId);
  const box = boxes.find((b) => b.node_id === boxId);
  const fname = freezer.label || freezer.code;
  const addrOf = (code: string) => `${fname} ${rack?.code}${layer?.code}:${box?.code},${code}`;

  const autoAssign = async () => {
    const { data } = await findFreeCells(freezer.node_id, autoN);
    if (data.count < autoN) message.warning(`该冰箱仅剩 ${data.count} 个空孔`);
    onChange?.({ mode: "auto", cellIds: data.cell_node_ids, addresses: data.addresses });
    message.success(`已分配 ${data.count} 个空孔`);
  };

  const onCellClick = (cellId: number, code: string, occupied: boolean) => {
    if (occupied) return;
    if (mode === "manual") {
      const m = new Map(picked);
      if (m.has(cellId)) m.delete(cellId); else m.set(cellId, addrOf(code));
      setPicked(m);
      onChange?.({ mode: "manual", cellIds: [...m.keys()], addresses: [...m.values()] });
    } else if (mode === "from") {
      const sc = { id: cellId, addr: addrOf(code) };
      setStartCell(sc);
      onChange?.({ mode: "from", startCellId: sc.id, startAddr: sc.addr, count: fromN });
    }
  };

  const selectedIds = useMemo(() => {
    if (mode === "manual") return new Set(picked.keys());
    if (mode === "from" && startCell) return new Set([startCell.id]);
    return new Set<number>();
  }, [mode, picked, startCell]);

  const cascade = (
    <Space wrap style={{ marginBottom: 12 }}>
      <Select placeholder="架" style={{ width: 80 }} value={rackId}
        options={racks.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
        onChange={(v) => { setRackId(v); setLayerId(undefined); setBoxId(undefined); }} />
      <Select placeholder="层" style={{ width: 80 }} value={layerId} disabled={rackId === undefined}
        options={layers.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
        onChange={(v) => { setLayerId(v); setBoxId(undefined); }} />
      <Select placeholder="盒区" style={{ width: 90 }} value={boxId} disabled={layerId === undefined}
        options={boxes.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
        onChange={(v) => setBoxId(v)} />
    </Space>
  );

  return (
    <div>
      <Segmented
        value={mode}
        onChange={(v) => changeMode(v as typeof mode)}
        options={[
          { label: "自动分配", value: "auto" },
          { label: "起始填充", value: "from" },
          { label: "手动选孔", value: "manual" },
        ]}
        style={{ marginBottom: 12 }}
      />

      {mode === "auto" && (
        <Space>
          <span>数量</span>
          <InputNumber min={1} max={5000} value={autoN} onChange={(v) => setAutoN(v ?? 1)} />
          <Button onClick={autoAssign}>自动分配空孔</Button>
        </Space>
      )}

      {mode === "from" && (
        <>
          <Space style={{ marginBottom: 8 }}>
            <span>数量</span>
            <InputNumber min={1} max={5000} value={fromN}
              onChange={(v) => {
                const n = v ?? 1; setFromN(n);
                onChange?.({ mode: "from", startCellId: startCell?.id, startAddr: startCell?.addr, count: n });
              }} />
            <span style={{ color: "#888" }}>在热力图中点一个空孔作为起始</span>
          </Space>
          {cascade}
          {boxId !== undefined && (
            <CellGrid cells={cells} selectedIds={selectedIds}
              onCellClick={(c) => onCellClick(c.cell_node_id, c.code, c.occupied)} />
          )}
          <Alert
            type={startCell ? "success" : "info"}
            showIcon
            style={{ marginTop: 12 }}
            message={startCell
              ? `从 ${startCell.addr} 起连续填充 ${fromN} 个孔(提交时校验须全空)`
              : "请点选起始孔"}
          />
        </>
      )}

      {mode === "manual" && (
        <>
          {cascade}
          {boxId !== undefined && (
            <CellGrid cells={cells} selectedIds={selectedIds}
              onCellClick={(c) => onCellClick(c.cell_node_id, c.code, c.occupied)} />
          )}
          <div style={{ marginTop: 12 }}>
            {picked.size === 0 ? (
              <Alert type="info" showIcon message="点选空孔(可多选)" />
            ) : (
              <Space size={[4, 4]} wrap>
                <span>已选 <b>{picked.size}</b>:</span>
                {[...picked.values()].slice(0, 40).map((a) => <Tag key={a} color="blue">{a}</Tag>)}
                {picked.size > 40 && <Tag>…共 {picked.size}</Tag>}
              </Space>
            )}
          </div>
        </>
      )}
    </div>
  );
}
