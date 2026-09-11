/**
 * 带右边缘拖拽手柄的表头单元格，配合 useResizableColumns 使用（2026-09-11）。
 * 单独成文件是因为 eslint react-refresh 规则不允许同一文件既导出 hook 又定义组件。
 *
 * 用 Pointer Events + setPointerCapture 而不是 mousedown + document 监听：
 * 按下后所有移动都定向发给手柄本身，鼠标划出表格、划出窗口都不会丢；
 * 触摸屏、触控笔同样可用；也不必手工加/摘 document 监听。
 */
import { useRef } from 'react';

const MIN_WIDTH = 60;
const MAX_WIDTH = 900;

interface HeaderCellProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  width?: number;
  onResize?: (width: number) => void;
  onResizeEnd?: (width: number) => void;
}

export function ResizableHeaderCell({
  width,
  onResize,
  onResizeEnd,
  style,
  children,
  ...rest
}: HeaderCellProps) {
  const startX = useRef(0);
  const startW = useRef(0);
  const latest = useRef(0);
  const dragging = useRef(false);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation(); // 别触发表头的排序点击
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* 个别环境（含自动化脚本注入的合成事件）拿不到指针捕获，不影响后续 move/up */
    }
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width ?? 0;
    latest.current = startW.current;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    const next = Math.min(
      MAX_WIDTH,
      Math.max(MIN_WIDTH, startW.current + e.clientX - startX.current),
    );
    latest.current = next;
    onResize?.(next);
  };

  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    dragging.current = false;
    try {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    } catch {
      /* 同上 */
    }
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    onResizeEnd?.(latest.current);
  };

  if (!width || !onResize) {
    return (
      <th style={style} {...rest}>
        {children}
      </th>
    );
  }

  return (
    <th style={{ ...style, position: 'relative' }} {...rest}>
      {children}
      <div
        role="separator"
        aria-orientation="vertical"
        title="拖动调整列宽"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'absolute',
          // 必须整个落在单元格内：带 ellipsis 的表头是 overflow:hidden，
          // 手柄若探出边界（right 取负值）会被裁掉，点不到（2026-09-11 实测）
          right: 0,
          top: 0,
          bottom: 0,
          width: 8,
          cursor: 'col-resize',
          userSelect: 'none',
          touchAction: 'none',
          zIndex: 2,
        }}
      />
    </th>
  );
}
