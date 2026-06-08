import { Tooltip } from "antd";
import type { Cell } from "../../../api/storage";

/**
 * 孔位热力图(展示用): 红=已占用, 蓝=已选中, 灰=空闲。
 * onCellClick 由父级按 cell.occupied 决定行为(空孔选中 / 占用孔释放)。
 */
interface Props {
  cells: Cell[];
  selectedIds?: Set<number>;
  onCellClick?: (cell: Cell) => void;
}

export default function CellGrid({ cells, selectedIds, onCellClick }: Props) {
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
        const bg = c.occupied ? "#ffccc7" : selected ? "#1F4E79" : "#f0f0f0";
        const color = selected ? "#fff" : c.occupied ? "#a8071a" : "#666";
        const square = (
          <div
            key={c.cell_node_id}
            onClick={() => onCellClick?.(c)}
            style={{
              width: 26, height: 26, lineHeight: "26px", textAlign: "center",
              fontSize: 11, borderRadius: 3, background: bg, color,
              cursor: onCellClick ? "pointer" : "default", userSelect: "none",
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
