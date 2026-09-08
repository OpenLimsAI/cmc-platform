"use client";

import dynamic from "next/dynamic";
import { useMemo, useRef } from "react";
import type { SeriesPoint } from "@/lib/api";

// echarts 在模块加载时会用到 window，禁用 SSR
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

// 图上一条线。value 为 null 的点 = 断线标记（多段工艺记录之间的空档），echarts 在此处断开不连线
export interface ChartPoint {
  time_hours: number;
  value: number | null;
}
export interface ChartSeries {
  code: string;
  name: string;
  unit: string | null;
  points: (SeriesPoint | ChartPoint)[];
  // 多批次叠图的区分规则（负责人 2026-09-08 定）：颜色 = 罐/批次（group），线型 + 标记形状 = 指标（kind）。
  // 不传时退回"每条线一个颜色"。
  group?: string; // 批次身份，如 016_R2604_A6
  kind?: string; // 指标代号，如 viable_per_ml
}

export interface ViewWindow {
  min: number;
  max: number;
}

const COLORS = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
  "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5",
  "#0d9488", "#b45309", "#9333ea", "#be123c", "#475569",
];

// 指标样式：第 1 个指标实线圆点、第 2 个虚线方块、第 3 个点线三角……（按勾选顺序轮转）
const KIND_STYLES: { symbol: string; type: "solid" | "dashed" | "dotted" }[] = [
  { symbol: "circle", type: "solid" },
  { symbol: "rect", type: "dashed" },
  { symbol: "triangle", type: "dotted" },
  { symbol: "diamond", type: "solid" },
  { symbol: "pin", type: "dashed" },
  { symbol: "arrow", type: "dotted" },
];

const pad2 = (n: number) => (n < 10 ? `0${n}` : String(n));

// 把 UTC 毫秒转成北京时间（UTC+8）「YYYY-MM-DD HH:mm」
function fmtBeijing(ms: number): string {
  const d = new Date(ms + 8 * 3600_000);
  return (
    `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ` +
    `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`
  );
}

// echarts tooltip（trigger:axis）回调拿到的单条 series 参数（只用到这几个字段）
interface TooltipParam {
  axisValue: number;
  marker: string;
  seriesName: string;
  value: number | number[];
}

export function SeriesChart({
  series,
  loading,
  fullRange,
  viewWindow,
  onWindowChange,
  xName = "培养时间 (h)",
  xTickInterval,
  hoursAxis = false,
  startTime,
  markers = false,
}: {
  series: ChartSeries[];
  loading?: boolean;
  // 该批次通道的完整时间范围（小时），用于缩放百分比 <-> 时间窗口换算
  fullRange?: ViewWindow | null;
  // 当前可见窗口（父组件单一数据源）；null = 全览
  viewWindow?: ViewWindow | null;
  // 缩放停稳后回调，null 表示回到全览
  onWindowChange?: (win: ViewWindow | null) => void;
  // 横轴名。工艺曲线用「培养时间 (h)」，细胞生长曲线用「培养天 (day)」
  xName?: string;
  // 横轴刻度固定间隔（工艺曲线传 24 = 每 24 小时一格；不传则 echarts 自动定刻度）
  xTickInterval?: number;
  // 横轴是培养小时（工艺全量时序）：tooltip 顶部补「第 N 天 · N h」
  hoursAxis?: boolean;
  // 批次开始时刻（ISO，单批次时传）：tooltip 顶部再补北京时间
  startTime?: string | null;
  // 在数据点上画标记（按天/按时段这类点少的图开；全量时序几千个点别开）
  markers?: boolean;
}) {
  const instRef = useRef<echartsInstance | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const option = useMemo(() => {
    // 只保留横轴有限的点；纵轴 NaN/Infinity 去掉（会让 echarts 算坐标轴时崩溃），null 保留当断线标记
    const clean = series.map((s) => ({
      ...s,
      points: s.points.filter(
        (p) => Number.isFinite(p.time_hours) && (p.value === null || Number.isFinite(p.value))
      ),
    }));

    // 按单位分组，每个不同单位一条 Y 轴（温度/pH/溶氧刻度不同也能看清）
    const units: string[] = [];
    const extent = new Map<string, { min: number; max: number }>();
    for (const s of clean) {
      const u = s.unit || "无单位";
      if (!units.includes(u)) units.push(u);
      const e = extent.get(u) ?? { min: Infinity, max: -Infinity };
      for (const p of s.points) {
        if (p.value === null) continue;
        if (p.value < e.min) e.min = p.value;
        if (p.value > e.max) e.max = p.value;
      }
      extent.set(u, e);
    }

    const yAxis = units.map((u, i) => {
      const e = extent.get(u)!;
      // 常量通道（min==max）或无数据时，手动给个范围，否则 echarts 会算出非法刻度
      let min: number | undefined;
      let max: number | undefined;
      if (!Number.isFinite(e.min) || !Number.isFinite(e.max)) {
        min = 0;
        max = 1;
      } else if (e.min === e.max) {
        const pad = Math.abs(e.min) > 1 ? Math.abs(e.min) * 0.1 : 1;
        min = e.min - pad;
        max = e.max + pad;
      }
      return {
        type: "value" as const,
        name: u === "无单位" ? "" : u, // pH 这类没单位的轴不写"无单位"
        nameGap: 18,
        position: i === 0 ? ("left" as const) : ("right" as const),
        offset: i <= 1 ? 0 : (i - 1) * 56,
        min,
        max,
        scale: true,
        axisLine: {
          show: true,
          lineStyle: { color: COLORS[i % COLORS.length] },
        },
        splitLine: { show: i === 0 },
      };
    });

    // 缩放位置（百分比）由 viewWindow 换算，保证视图与所取数据窗口一致
    let zStart = 0;
    let zEnd = 100;
    if (viewWindow && fullRange && fullRange.max > fullRange.min) {
      const span = fullRange.max - fullRange.min;
      zStart = ((viewWindow.min - fullRange.min) / span) * 100;
      zEnd = ((viewWindow.max - fullRange.min) / span) * 100;
    }
    const z = { start: zStart, end: zEnd };

    // 横轴是培养小时时（工艺曲线），tooltip 顶部除小时外再补「第 N 天」（+ 单批次时的北京时间）。
    // 天数规则：0h=第0天，满 24h 进第 1 天 → floor(小时/24)。
    const baseMs = startTime ? new Date(startTime).getTime() : NaN;
    const tooltip = hoursAxis || startTime
      ? {
          trigger: "axis" as const,
          axisPointer: { type: "cross" as const },
          formatter: (params: TooltipParam[]) => {
            if (!params.length) return "";
            const hours = Number(params[0].axisValue);
            const day = Math.floor(hours / 24);
            let head = `第 ${day} 天 · ${hours.toFixed(2)} h`;
            if (Number.isFinite(baseMs)) {
              head += ` · 北京时间 ${fmtBeijing(baseMs + hours * 3600_000)}`;
            }
            const rows = params
              .map((p) => {
                const y = Array.isArray(p.value) ? p.value[1] : p.value;
                const vs = typeof y === "number" ? y.toFixed(3) : y;
                return `<div>${p.marker}${p.seriesName}: <b>${vs}</b></div>`;
              })
              .join("");
            return `<div style="font-weight:600;margin-bottom:4px">${head}</div>${rows}`;
          },
        }
      : {
          trigger: "axis" as const,
          axisPointer: { type: "cross" as const },
          valueFormatter: (v: number) =>
            typeof v === "number" ? v.toFixed(3) : v,
        };

    // 颜色 = 批次（多批次时），线型 + 标记 = 指标；只有一个批次时仍按线分颜色（更好认）
    const groups: string[] = [];
    const kinds: string[] = [];
    for (const s of clean) {
      if (s.group && !groups.includes(s.group)) groups.push(s.group);
      if (s.kind && !kinds.includes(s.kind)) kinds.push(s.kind);
    }
    const multiGroup = groups.length > 1;

    return {
      animation: false,
      color: COLORS,
      tooltip,
      // 图例贴顶、绘图区往下让 —— 中间留出空隙给纵轴的单位名，免得和图例挤在一起
      legend: { top: 4, type: "scroll" as const },
      grid: {
        top: 84,
        left: 56,
        right: Math.max(56, (units.length - 1) * 56 + 16),
        bottom: 64,
        containLabel: true,
      },
      xAxis: {
        type: "value" as const,
        name: xName,
        nameLocation: "middle" as const,
        nameGap: 28,
        min: fullRange ? fullRange.min : 0,
        max: fullRange ? fullRange.max : undefined,
        // 传了固定间隔（如 24h）就每格对齐，否则让 echarts 自动定
        interval: xTickInterval,
        axisLabel: {
          formatter: (v: number) => (Math.round(v * 10) / 10).toString(),
        },
      },
      yAxis,
      dataZoom: [
        // filterMode:"none" —— 缩放只改视野、不过滤数据点（Y 轴范围稳定）；
        // start/end 从 zoomRef 读，图重建时保持用户当前的缩放位置
        {
          type: "inside" as const,
          filterMode: "none" as const,
          start: z.start,
          end: z.end,
        },
        {
          type: "slider" as const,
          height: 20,
          bottom: 20,
          filterMode: "none" as const,
          start: z.start,
          end: z.end,
        },
      ],
      series: clean.map((s, i) => {
        const gi = s.group ? groups.indexOf(s.group) : -1;
        const ki = s.kind ? kinds.indexOf(s.kind) : -1;
        const color = multiGroup && gi >= 0 ? COLORS[gi % COLORS.length] : COLORS[i % COLORS.length];
        const style = ki >= 0 ? KIND_STYLES[ki % KIND_STYLES.length] : KIND_STYLES[0];
        return {
          name: `${s.name || s.code}${s.unit ? " (" + s.unit + ")" : ""}`,
          type: "line" as const,
          color,
          symbol: markers ? style.symbol : "none",
          symbolSize: 7,
          showSymbol: markers,
          lineStyle: { width: 2, type: multiGroup ? style.type : "solid" },
          smooth: false,
          connectNulls: false,
          // 鼠标悬停到某条线（或图例），其他线变淡，只突出这一条
          emphasis: { focus: "series" as const, lineStyle: { width: 3 } },
          blur: { lineStyle: { opacity: 0.12 }, itemStyle: { opacity: 0.12 } },
          yAxisIndex: units.indexOf(s.unit || "无单位"),
          data: s.points.map((p) => [p.time_hours, p.value]),
        };
      }),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, fullRange, viewWindow, xName, xTickInterval, hoursAxis, startTime, markers]);

  function handleDataZoom() {
    const inst = instRef.current;
    if (!inst || !fullRange) return;
    const opt = inst.getOption() as { dataZoom?: Array<{ start?: number; end?: number }> };
    const dz = opt.dataZoom?.[0];
    if (!dz) return;
    const start = dz.start ?? 0;
    const end = dz.end ?? 100;

    // 防抖：拖动过程中不发请求，停稳 300ms 后才按新窗口取数
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const span = fullRange.max - fullRange.min;
      const isFull = start <= 0.5 && end >= 99.5;
      onWindowChange?.(
        isFull
          ? null
          : {
              min: fullRange.min + (start / 100) * span,
              max: fullRange.min + (end / 100) * span,
            }
      );
    }, 300);
  }

  if (!series.length) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        {loading ? "加载中…" : "勾选要看的指标 / 通道"}
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      {loading && (
        <div className="absolute right-3 top-1 z-10 text-xs text-slate-400">
          更新中…
        </div>
      )}
      <ReactECharts
        option={option}
        style={{ height: "100%", width: "100%" }}
        notMerge
        opts={{ renderer: "canvas" }}
        onChartReady={(inst: echartsInstance) => {
          instRef.current = inst;
        }}
        onEvents={{ datazoom: handleDataZoom }}
      />
    </div>
  );
}

// echarts 实例的最小类型（避免额外引入 echarts 类型依赖）
interface echartsInstance {
  getOption: () => unknown;
}
