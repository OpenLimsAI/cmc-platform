import { Card, Empty, theme } from 'antd';
import { useApplicationTheme } from '@/shared/applicationThemeContext';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import type { DashboardSummary } from '@/api/types';

interface Props {
  trend: DashboardSummary['trend_30d'];
}

const SERIES_META: { key: keyof DashboardSummary['trend_30d']; name: string; color: string }[] = [
  { key: 'substance', name: '物质', color: '#1e466b' },
  { key: 'project', name: '项目', color: '#3b7ea8' },
  { key: 'asset', name: '资产', color: '#67baf4' },
  { key: 'material', name: '物料', color: '#536c80' },
  { key: 'equipment', name: '设备', color: '#90b9d4' },
  { key: 'target', name: '靶点', color: '#36617f' },
];

export function TrendLineCard({ trend }: Props) {
  const { dark } = useApplicationTheme();
  const { token } = theme.useToken();
  // x 轴用第一个 series 的日期序列（4 域日期对齐）
  // 2026-09-10：按读权限裁剪后 trend 只含可见域，只画有的；x 轴取第一个有的域
  const series_meta = SERIES_META.filter((m) => Array.isArray(trend[m.key]));
  const first = series_meta.length ? trend[series_meta[0].key] ?? [] : [];
  const xLabels = first.map((p) => dayjs(p.date).format('MM-DD'));
  const totalNew = series_meta.reduce(
    (acc, m) => acc + (trend[m.key] ?? []).reduce((s, p) => s + p.count, 0),
    0,
  );

  if (totalNew === 0) {
    return (
      <Card title="近 30 天新增趋势">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="近 30 天暂无新增记录"
        />
      </Card>
    );
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: series_meta.map((s) => s.name), top: 0 },
    grid: { left: 40, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: xLabels, boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1 },
    series: series_meta.map((m) => ({
      name: m.name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: m.color },
      areaStyle: { opacity: 0.08, color: m.color },
      data: (trend[m.key] ?? []).map((p) => p.count),
    })),
  };

  return (
    <Card title="近 30 天新增趋势" extra={<span style={{ color: token.colorTextSecondary }}>共新增 {totalNew} 条</span>}>
      <ReactECharts theme={dark ? 'dark' : undefined} option={option} style={{ height: 320 }} />
    </Card>
  );
}
