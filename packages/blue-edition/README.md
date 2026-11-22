# `@maibo/blue-edition`

迈博药业（Mabpharm / CMAB）**MBERP 设计规范 v2.0（Swiss Clinical Precision）** 前端共享主题包，面向 `cmc-platform` 全部 Web 子系统（`cmab-mdm-platform`、`cmc-water-system-dashboard`、`cmc-platform-monitor`、`cmc-quality-analytics-platform`、`cmc-rd-lims-dashboard`、`cmc-rd-usp-dashboard`、`cmc-labops`）。

## 核心设计标准

1. **强制浅色与 90-8-2 用色法则**：锁定 `color-scheme: only light`，90% 冷灰白中性层（画布 `#F6F8FA` / 工作面 `#FFFFFF`）+ 8% 迈博深海蓝 `#1E466B` + 2% GxP 高对比语义状态色。
2. **瑞士精密仪器几何尺度**：容器/卡片圆角收紧至 `6px`，按钮/输入框/标签圆角 `4px`，顶栏统一 `56px`，以 `1px solid #D8E0E8` 锐利微边框取代弥散阴影。
3. **全局数字等宽对齐（`tabular-nums`）**：表格单元格、统计指标、批号、电导率、TOC、pH、库存与日期强制启用 `font-variant-numeric: tabular-nums`。
4. **严格作用域边界**：`cmc-platform` 全部业务系统均属于研发/质量精密台账与看板，严禁混入衬线字体或暖黄阅读底色。

## 目录结构

- `tokens.css`：标准 CSS 自定义属性（`--workbench-*`、`--cmc-*`、`--status-*`）及 `.tnum` / `.mono-id` 数字等宽规则。
- `antdTheme.ts`：兼容 Ant Design 5 与 Ant Design 6 `<ConfigProvider>` 的 `maiboSwissAntdTheme` 预设与 `MAIBO_SWISS_TOKENS` / `MAIBO_CHART_PALETTE` 常量。
- `index.ts`：TypeScript 统一导出入口。

## 使用方式

### 1. Ant Design 5 / 6 子系统（MDM / Water / QAP / LabOps）

```tsx
import '@maibo/blue-edition/tokens.css';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { maiboSwissAntdTheme } from '@maibo/blue-edition';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider locale={zhCN} theme={maiboSwissAntdTheme}>
      {children}
    </ConfigProvider>
  );
}
```

### 2. 原生 CSS / Tailwind v4 子系统（Ops / LIMS / USP）

直接在全局样式入口引入 `@maibo/blue-edition/tokens.css`，消费 `--cmc-canvas`、`--cmc-surface`、`--cmc-border`、`--cmc-primary` 等变量即可保持跨应用视觉一致。
