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
  color?: string; // 该指标的固定颜色（单批次时用；不传按出现顺序取调色板）
  shape?: number; // 该指标的固定线型/标记序号（多批次时用；不传按指标出现顺序取）
  axis?: "left" | "right"; // 这条线的纵轴想放哪边（同一单位共用一根轴，以第一条线的意愿为准）
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

// scheme="metric" 时用来区分不同罐/批次的标记形状（颜色留给指标）；CurveSection 的罐号图例按同一顺序画图标
export const GROUP_SYMBOLS = ["circle", "rect", "triangle", "diamond", "pin", "arrow", "roundRect"];

// 右侧第 2、3… 根纵轴各占的宽度（像素）
const EXTRA_AXIS_W = 56;

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
  scheme = "batch",
  showLegend = true,
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
  // 多批次叠图怎么区分：
  //   "batch"  颜色 = 罐/批次，线型 + 标记 = 指标（默认）
  //   "metric" 颜色 = 指标（固定色）、全部实线，标记形状 = 罐/批次（生长曲线用）
  scheme?: "batch" | "metric";
  // 图内自带的图例；页面上已用指标按钮当图例时传 false，绘图区相应上移
  showLegend?: boolean;
}) {
  const instRef = useRef<EchartsInstance | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const option = useMemo(() => {
    // 只保留横轴有限的点；纵轴 NaN/Infinity 去掉（会让 echarts 算坐标轴时崩溃），null 保留当断线标记
    const clean = series.map((s) => ({
      ...s,
      points: s.points.filter(
        (p) => Number.isFinite(p.time_hours) && (p.value === null || Number.isFinite(p.value))
      ),
    }));

    // 按单位分组，每个不同单位一条 Y 轴（温度/pH/溶氧刻度不同也能看清）。
    // 轴的左右：指明要放左边的单位排最前（第 1 根轴在左，其余在右），其它按出现顺序。
    const units: string[] = [];
    const wantLeft = new Set<string>();
    const extent = new Map<string, { min: number; max: number }>();
    for (const s of clean) {
      const u = s.unit || "无单位";
      if (!units.includes(u)) {
        units.push(u);
        if (s.axis === "left") wantLeft.add(u);
      }
      const e = extent.get(u) ?? { min: Infinity, max: -Infinity };
      for (const p of s.points) {
        if (p.value === null) continue;
        if (p.value < e.min) e.min = p.value;
        if (p.value > e.max) e.max = p.value;
      }
      extent.set(u, e);
    }
    units.sort((a, b) => Number(wantLeft.has(b)) - Number(wantLeft.has(a)));

    // 颜色 = 批次（多批次时），线型 + 标记 = 指标；只有一个批次时颜色 = 指标固定色
    const groups: string[] = [];
    const kinds: string[] = [];
    for (const s of clean) {
      if (s.group && !groups.includes(s.group)) groups.push(s.group);
      if (s.kind && !kinds.includes(s.kind)) kinds.push(s.kind);
    }
    const multiGroup = scheme === "batch" && groups.length > 1;
    const seriesColor = clean.map((s, i) => {
      const gi = s.group ? groups.indexOf(s.group) : -1;
      return multiGroup && gi >= 0 ? COLORS[gi % COLORS.length] : s.color ?? COLORS[i % COLORS.length];
    });
    // 每条纵轴的颜色跟挂在它上面的第一条线走（活率的 % 轴就是活率的颜色）
    const axisColor = (u: string) => {
      const idx = clean.findIndex((s) => (s.unit || "无单位") === u);
      return idx >= 0 ? seriesColor[idx] : COLORS[0];
    };

    const yAxis = units.map((u, i) => {
      const e = extent.get(u)!;
      // 纵轴范围：数据只占轴高的 70%，上下各留 15%（负责人 2026-09-08 定，好看）。
      // 常量通道（min==max）或无数据时手动给个范围，否则 echarts 会算出非法刻度。
      let min: number;
      let max: number;
      if (!Number.isFinite(e.min) || !Number.isFinite(e.max)) {
        min = 0;
        max = 1;
      } else if (e.min === e.max) {
        const pad = Math.abs(e.min) > 1 ? Math.abs(e.min) * 0.1 : 1;
        min = e.min - pad;
        max = e.max + pad;
      } else {
        const pad = ((e.max - e.min) * 15) / 70;
        min = e.min - pad;
        max = e.max + pad;
        if (e.min >= 0 && min < 0) min = 0; // 密度、流量这类不会负的量，下边不越过 0
      }
      return {
        type: "value" as const,
        name: u === "无单位" ? "" : u, // pH 这类没单位的轴不写"无单位"
        nameGap: 18,
        position: i === 0 ? ("left" as const) : ("right" as const),
        offset: i <= 1 ? 0 : (i - 1) * EXTRA_AXIS_W,
        min: Math.round(min * 1000) / 1000,
        max: Math.round(max * 1000) / 1000,
        // 上下留白后轴的端点不是整数（73.447 这种），不标端点，只标中间的整刻度
        axisLabel: { showMinLabel: false, showMaxLabel: false },
        axisLine: {
          show: true,
          lineStyle: { color: axisColor(u) },
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

    return {
      animation: false,
      color: COLORS,
      tooltip,
      // 图例贴顶、绘图区往下让 —— 中间留出空隙给纵轴的单位名，免得和图例挤在一起
      legend: { show: showLegend, top: 4, type: "scroll" as const },
      grid: {
        top: showLegend ? 84 : 40,
        left: 56,
        // 右边：多余的 Y 轴各占 EXTRA_AXIS_W
        right: Math.max(56, (units.length - 1) * EXTRA_AXIS_W + 16),
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
        // [0] 横轴：滚轮 / 拖图 = 缩放平移。filterMode:"none" —— 缩放只改视野、不过滤数据点（Y 轴范围稳定）
        {
          type: "inside" as const,
          filterMode: "none" as const,
          start: z.start,
          end: z.end,
        },
        // [1] 横轴底部滑块
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
        const ki = s.kind ? kinds.indexOf(s.kind) : -1;
        const gi = s.group ? groups.indexOf(s.group) : -1;
        const color = seriesColor[i];
        // batch 方案：单批次颜色 = 指标固定色；多批次颜色 = 罐，线型/标记 = 指标固定形状
        // metric 方案：颜色 = 指标固定色、全部实线，标记形状 = 罐
        const si = s.shape ?? (ki >= 0 ? ki : 0);
        const style =
          scheme === "metric"
            ? { symbol: GROUP_SYMBOLS[(gi >= 0 ? gi : 0) % GROUP_SYMBOLS.length], type: "solid" as const }
            : KIND_STYLES[si % KIND_STYLES.length];
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
  }, [series, fullRange, viewWindow, xName, xTickInterval, hoursAxis, startTime, markers, scheme, showLegend]);

  // 横轴缩放后：防抖，停稳再按新窗口取数
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
      const next = isFull
        ? null
        : { min: fullRange.min + (start / 100) * span, max: fullRange.min + (end / 100) * span };
      // 没变就不通知
      const same =
        (next === null && !viewWindow) ||
        (next && viewWindow && Math.abs(next.min - viewWindow.min) < 1e-6 && Math.abs(next.max - viewWindow.max) < 1e-6);
      if (!same) onWindowChange?.(next);
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
        onChartReady={(inst: EchartsInstance) => {
          instRef.current = inst;
        }}
        onEvents={{ datazoom: handleDataZoom }}
      />
    </div>
  );
}

// echarts 实例的最小类型（避免额外引入 echarts 类型依赖）
interface EchartsInstance {
  getOption: () => unknown;
}
