import { Card, Empty, Typography } from 'antd';
import ReactECharts from 'echarts-for-react';
import type { DistributionItem } from '@/api/types';

const { Text } = Typography;

interface Props {
  title: string;
  data: DistributionItem[];
  /** key → 显示标签的映射；缺失时回退到 key 原样 */
  labelMap?: Record<string, string>;
  /** key → 颜色 */
  colorMap?: Record<string, string>;
  /** 'pie' 饼图（默认），'bar' 横向柱图（适合多类目如 asset_by_phase 9 阶段） */
  variant?: 'pie' | 'bar';
}

const FALLBACK_COLORS = [
  '#1F4E79', '#2E75B6', '#52C41A', '#FAAD14', '#F5222D',
  '#722ED1', '#13C2C2', '#EB2F96', '#A0D911', '#FA8C16',
];

function colorOf(key: string, idx: number, colorMap?: Record<string, string>): string {
  return colorMap?.[key] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

export function DistributionPieCard({
  title,
  data,
  labelMap,
  colorMap,
  variant = 'pie',
}: Props) {
  const filtered = data.filter((d) => d.count > 0);

  if (filtered.length === 0) {
    return (
      <Card title={title} style={{ height: '100%' }}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
      </Card>
    );
  }

  const labelize = (key: string | null) => {
    if (key === null || key === undefined || key === '') return '(未设置)';
    return labelMap?.[key] ?? key;
  };

  let option: object;
  if (variant === 'bar') {
    option = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 90, right: 30, top: 10, bottom: 30 },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: {
        type: 'category',
        data: filtered.map((d) => labelize(d.key)),
        axisLabel: { interval: 0 },
      },
      series: [
        {
          type: 'bar',
          data: filtered.map((d, idx) => ({
            value: d.count,
            itemStyle: { color: colorOf(d.key ?? '_null', idx, colorMap) },
          })),
          label: { show: true, position: 'right' },
          barMaxWidth: 22,
        },
      ],
    };
  } else {
    option = {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          type: 'pie',
          radius: ['45%', '70%'],
          avoidLabelOverlap: true,
          label: { show: true, formatter: '{b}\n{d}%' },
          data: filtered.map((d, idx) => ({
            name: labelize(d.key),
            value: d.count,
            itemStyle: { color: colorOf(d.key ?? '_null', idx, colorMap) },
          })),
        },
      ],
    };
  }

  return (
    <Card
      title={title}
      style={{ height: '100%' }}
      extra={<Text type="secondary">共 {filtered.reduce((s, d) => s + d.count, 0)} 条</Text>}
    >
      <ReactECharts option={option} style={{ height: 280 }} />
    </Card>
  );
}
