import { Tooltip } from "antd";
import type { Cell } from "../../../api/storage";

/**
 * 孔位热力图(展示用): 灰=空闲, 绿=已占用(在效期), 红=已占用且已过期, 蓝=已选中。
 * onCellClick 由父级按 cell.occupied 决定行为(空孔选中 / 占用孔释放)。
 *
 * ownBatchId 给"出库按盒选孔"用: 传入则只把该批次的孔当作可操作目标,
 * 其它物料占用的孔显示为暗灰且不可点(避免误选到别人的管子)。
 */
interface Props {
  cells: Cell[];
  selectedIds?: Set<number>;
  onCellClick?: (cell: Cell) => void;
  ownBatchId?: number | null;
}

export default function CellGrid({ cells, selectedIds, onCellClick, ownBatchId }: Props) {
  const cols = cells.length <= 81 ? 9 : 10;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 26px)`,
        gap: 4,
      }}
    >
      {cells.map((c) => {
        const selected = selectedIds?.has(c.cell_node_id);
        const expired = c.occupied && c.days_to_expiry != null && c.days_to_expiry < 0;
        // 出库模式:占用孔但不属于本批次 → 暗灰、不可选
        const otherBatch = c.occupied && ownBatchId != null && c.batch_id !== ownBatchId;
        // 是否可点:有 onCellClick;出库模式下只有本批次占用孔可点
        const clickable = !!onCellClick && (ownBatchId == null || (c.occupied && c.batch_id === ownBatchId));
        // 选中(蓝) > 他料(暗灰) > 已过期(红) > 已占用在效期(绿) > 空(灰)
        const bg = selected ? "#1F4E79"
          : otherBatch ? "#f5f5f5"
          : expired ? "#ffccc7"
          : c.occupied ? "#d9f7be"
          : "#f0f0f0";
        const color = selected ? "#fff"
          : otherBatch ? "#bfbfbf"
          : expired ? "#a8071a"
          : c.occupied ? "#389e0d"
          : "#666";
        const square = (
          <div
            key={c.cell_node_id}
            onClick={() => clickable && onCellClick?.(c)}
            style={{
              width: 26, height: 26, lineHeight: "26px", textAlign: "center",
              fontSize: 11, borderRadius: 3, background: bg, color,
              cursor: clickable ? "pointer" : "default", userSelect: "none",
              outline: selected ? "2px solid #0958d9" : undefined,
            }}
          >
            {c.code}
          </div>
        );
        return c.occupied ? (
          <Tooltip
            key={c.cell_node_id}
            title={
              <>
                <div>{c.material_code} {c.material_name}</div>
                <div>批号 {c.batch_no}</div>
                {c.sample_label && <div>样品 {c.sample_label}</div>}
                {c.expiry_date && (
                  <div>
                    有效期 {c.expiry_date}
                    {c.days_to_expiry != null && c.days_to_expiry < 0 && "(已过期)"}
                  </div>
                )}
                {otherBatch && <div>(其它物料,不可选)</div>}
              </>
            }
          >
            {square}
          </Tooltip>
        ) : square;
      })}
    </div>
  );
}
