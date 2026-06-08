import { useEffect, useMemo, useState } from "react";
import { Select, Space, Segmented, InputNumber, Button, Tag, Alert, message } from "antd";
import { useQuery } from "@tanstack/react-query";
import {
  listNodes, listCells, findFreeCells, type StorageNode,
} from "../../../api/storage";
import CellGrid from "../../storage/components/CellGrid";

/**
 * -80℃ 冻存入库选孔: 在某冰箱内选若干空孔。
 * value = 选中的 cell_node_id[]; onChange(ids) 上抛。
 * 两种方式:
 *   自动分配 — 输入 N, 调 free-cells 取连续空孔;
 *   手动选孔 — 架→层→盒级联 + 热力图点选空孔。
 */
interface Props {
  freezer: StorageNode;
  value?: number[];
  onChange?: (ids: number[]) => void;
}

export default function FreezerCellPicker({ freezer, value = [], onChange }: Props) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [autoN, setAutoN] = useState<number>(1);
  // 选中孔的 id→地址, 用于展示标签; 上抛只用 id
  const [picked, setPicked] = useState<Map<number, string>>(new Map());
  const [rackId, setRackId] = useState<number>();
  const [layerId, setLayerId] = useState<number>();
  const [boxId, setBoxId] = useState<number>();

  // 外部清空(form 重置 / 切冰箱) → 清内部
  useEffect(() => {
    if (value.length === 0 && picked.size > 0) setPicked(new Map());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.length]);
  // 切冰箱时重置级联
  useEffect(() => {
    setRackId(undefined); setLayerId(undefined); setBoxId(undefined);
    setPicked(new Map()); onChange?.([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [freezer.node_id]);

  const emit = (m: Map<number, string>) => {
    setPicked(m);
    onChange?.(Array.from(m.keys()));
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
    queryKey: ["fz", "cells", boxId, picked.size],
    queryFn: () => listCells(boxId!).then((r) => r.data),
    enabled: boxId !== undefined,
  });

  const rack = racks.find((r) => r.node_id === rackId);
  const layer = layers.find((l) => l.node_id === layerId);
  const box = boxes.find((b) => b.node_id === boxId);
  const selectedIds = useMemo(() => new Set(picked.keys()), [picked]);

  const autoAssign = async () => {
    const { data } = await findFreeCells(freezer.node_id, autoN);
    if (data.count < autoN) {
      message.warning(`该冰箱仅剩 ${data.count} 个空孔`);
    }
    const m = new Map<number, string>();
    data.cell_node_ids.forEach((id, i) => m.set(id, data.addresses[i]));
    emit(m);
  };

  const toggleCell = (cellId: number, code: string, occupied: boolean) => {
    if (occupied) return;
    const m = new Map(picked);
    if (m.has(cellId)) m.delete(cellId);
    else m.set(cellId, `${freezer.label || freezer.code} ${rack?.code}${layer?.code}:${box?.code},${code}`);
    emit(m);
  };

  return (
    <div>
      <Segmented
        value={mode}
        onChange={(v) => { setMode(v as "auto" | "manual"); emit(new Map()); }}
        options={[
          { label: "自动分配", value: "auto" },
          { label: "手动选孔", value: "manual" },
        ]}
        style={{ marginBottom: 12 }}
      />

      {mode === "auto" ? (
        <Space>
          <span>数量</span>
          <InputNumber min={1} max={5000} value={autoN} onChange={(v) => setAutoN(v ?? 1)} />
          <Button onClick={autoAssign}>自动分配空孔</Button>
        </Space>
      ) : (
        <Space wrap style={{ marginBottom: 12 }}>
          <Select
            placeholder="架" style={{ width: 90 }} value={rackId}
            options={racks.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
            onChange={(v) => { setRackId(v); setLayerId(undefined); setBoxId(undefined); }}
          />
          <Select
            placeholder="层" style={{ width: 90 }} value={layerId} disabled={rackId === undefined}
            options={layers.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
            onChange={(v) => { setLayerId(v); setBoxId(undefined); }}
          />
          <Select
            placeholder="盒区" style={{ width: 100 }} value={boxId} disabled={layerId === undefined}
            options={boxes.map((n) => ({ label: n.label || n.code, value: n.node_id }))}
            onChange={(v) => setBoxId(v)}
          />
        </Space>
      )}

      {mode === "manual" && boxId !== undefined && (
        <div style={{ marginTop: 8 }}>
          <CellGrid
            cells={cells}
            selectedIds={selectedIds}
            onCellClick={(c) => toggleCell(c.cell_node_id, c.code, c.occupied)}
          />
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        {picked.size === 0 ? (
          <Alert type="info" showIcon message="尚未选择孔位" />
        ) : (
          <>
            <div style={{ marginBottom: 6 }}>已选 <b>{picked.size}</b> 个孔:</div>
            <Space size={[4, 4]} wrap>
              {Array.from(picked.values()).slice(0, 60).map((addr) => (
                <Tag key={addr} color="blue">{addr}</Tag>
              ))}
              {picked.size > 60 && <Tag>…共 {picked.size} 个</Tag>}
            </Space>
          </>
        )}
      </div>
    </div>
  );
}
