import { Card, Empty } from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import type { DashboardSummary } from '@/api/types';

interface Props {
  trend: DashboardSummary['trend_30d'];
}

const SERIES_META: { key: keyof DashboardSummary['trend_30d']; name: string; color: string }[] = [
  { key: 'substance', name: '物质', color: '#1F4E79' },
  { key: 'project', name: '项目', color: '#52C41A' },
  { key: 'asset', name: '资产', color: '#FAAD14' },
  { key: 'material', name: '物料', color: '#722ED1' },
];

export function TrendLineCard({ trend }: Props) {
  // x 轴用第一个 series 的日期序列（4 域日期对齐）
  const xLabels = trend.substance.map((p) => dayjs(p.date).format('MM-DD'));
  const totalNew = SERIES_META.reduce(
    (acc, m) => acc + trend[m.key].reduce((s, p) => s + p.count, 0),
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
    tooltip: { trigger: 'axis' },
    legend: { data: SERIES_META.map((s) => s.name), top: 0 },
    grid: { left: 40, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: xLabels, boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1 },
    series: SERIES_META.map((m) => ({
      name: m.name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: m.color },
      areaStyle: { opacity: 0.08, color: m.color },
      data: trend[m.key].map((p) => p.count),
    })),
  };

  return (
    <Card title="近 30 天新增趋势" extra={<span style={{ color: '#8c8c8c' }}>共新增 {totalNew} 条</span>}>
      <ReactECharts option={option} style={{ height: 320 }} />
    </Card>
  );
}
