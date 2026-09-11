/**
 * 可拖拽调整列宽的表格列（2026-09-11）
 *
 * 用法：
 *   const { columns, components, resetWidths, isCustomized } = useResizableColumns('equipments', BASE_COLUMNS);
 *   <Table columns={columns} components={components} ... />
 *
 * 行为：
 *   - 表头右边缘拖拽改列宽，松手即记住
 *   - 按「登录人 + 表名」分别记在本机浏览器里（localStorage），换人登录互不影响
 *   - 列定义里改了默认宽度、或新增/删除了列，不会影响用户已经调过的其它列
 *   - 只存用户**真的动过**的列，没动过的跟着代码里的默认值走（以后调默认值能立刻生效）
 *
 * 不引第三方依赖（react-resizable 之类），自己处理 mousedown/mousemove，代码量也就几十行。
 * 存在浏览器本地属于「个人偏好」，清了浏览器数据就回到默认宽度，不影响业务数据。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { ResizableHeaderCell } from './ResizableHeaderCell';

const STORAGE_KEY = 'cmab_mdm_col_widths';

type WidthMap = Record<string, number>;

function readAll(): Record<string, WidthMap> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Record<string, WidthMap>;
  } catch {
    return {};
  }
}

function writeScope(scope: string, widths: WidthMap): void {
  try {
    const all = readAll();
    if (Object.keys(widths).length === 0) delete all[scope];
    else all[scope] = widths;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    /* 隐私模式 / 存储被禁用：不记住就是了，不影响使用 */
  }
}

type AnyColumn = { key?: React.Key; dataIndex?: unknown; width?: number };

export function useResizableColumns<C extends AnyColumn>(tableId: string, baseColumns: C[]) {
  const username = useAuthStore((s) => s.user?.username) ?? 'anonymous';
  const scope = `${username}:${tableId}`;

  const [widths, setWidths] = useState<WidthMap>(() => readAll()[scope] ?? {});
  // 换人登录时切换到那个人的设置
  useEffect(() => {
    setWidths(readAll()[scope] ?? {});
  }, [scope]);

  const colKey = useCallback(
    (c: C, i: number) => String(c.key ?? (c.dataIndex as string | undefined) ?? i),
    [],
  );

  const setWidth = useCallback((key: string, w: number, persist: boolean) => {
    setWidths((prev) => {
      const next = { ...prev, [key]: w };
      if (persist) writeScope(scope, next);
      return next;
    });
  }, [scope]);

  const resetWidths = useCallback(() => {
    setWidths({});
    writeScope(scope, {});
  }, [scope]);

  const columns = useMemo(
    () =>
      baseColumns.map((c, i) => {
        const key = colKey(c, i);
        const width = widths[key] ?? c.width;
        return {
          ...c,
          width,
          onHeaderCell: () => ({
            width,
            onResize: (w: number) => setWidth(key, w, false),
            onResizeEnd: (w: number) => setWidth(key, w, true),
          }),
        };
      }),
    [baseColumns, widths, colKey, setWidth],
  );

  // 只替换表头单元格，与行数据类型无关；不加显式注解，让它能配任意行类型的 Table
  const components = useMemo(() => ({ header: { cell: ResizableHeaderCell } }), []);

  /** 表格总宽：用于 scroll.x，保证拖宽后能横向滚动而不是被压扁 */
  const totalWidth = useMemo(
    () => columns.reduce((sum, c) => sum + (typeof c.width === 'number' ? c.width : 120), 0),
    [columns],
  );

  return {
    columns,
    components,
    resetWidths,
    totalWidth,
    isCustomized: Object.keys(widths).length > 0,
  };
}
