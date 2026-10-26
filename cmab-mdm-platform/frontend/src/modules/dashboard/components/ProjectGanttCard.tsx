import { Card, Empty, Tag, Tooltip, Typography } from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';
import type { GanttProject } from '@/api/types';

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  proposed: '#8c8c8c',
  initiated: '#1F4E79',
  active: '#52C41A',
  on_hold: '#FAAD14',
  completed: '#13C2C2',
  terminated: '#F5222D',
  cancelled: '#8c8c8c',
};

const STATUS_LABEL: Record<string, string> = {
  proposed: '提案',
  initiated: '启动',
  active: '进行中',
  on_hold: '暂停',
  completed: '完成',
  terminated: '终止',
  cancelled: '取消',
};

interface Props {
  projects: GanttProject[];
}

interface RenderApiParams {
  context: { rect?: { x: number; y: number; width: number; height: number } };
  coord: (point: [unknown, unknown]) => [number, number];
  size: (sizes: [unknown, unknown]) => [number, number];
}

interface RenderApi {
  value: (idx: number) => unknown;
  coord: (point: [unknown, unknown]) => [number, number];
  size: (sizes: [unknown, unknown], dataIndex?: number) => [number, number];
  style: (extra?: object) => object;
}

export function ProjectGanttCard({ projects }: Props) {
  const navigate = useNavigate();

  if (projects.length === 0) {
    return (
      <Card title="项目甘特图">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可显示的项目时间线" />
      </Card>
    );
  }

  // 为每个项目准备一行；x 轴是时间（自动），y 是项目 index
  // ECharts custom series：每条数据 [yIdx, startTs, endTs, status, projectName]
  const projectRows = projects.map((p) => {
    const startStr = p.actual_start_date ?? p.planned_start_date;
    const endStr = p.actual_end_date ?? p.planned_end_date;
    const start = startStr ? dayjs(startStr) : dayjs();
    const end = endStr ? dayjs(endStr) : start.add(30, 'day');
    return {
      project: p,
      start,
      end: end.isAfter(start) ? end : start.add(1, 'day'),
    };
  });

  const data = projectRows.map((row, idx) => [
    idx,
    row.start.valueOf(),
    row.end.valueOf(),
    row.project.status,
    row.project.project_name,
    row.project.project_code,
  ]);

  // 里程碑散点：所有项目的 milestones 平铺 → [yIdx, planned_ts, actual_or_null, name]
  const milestonePoints: Array<[number, number, string, string]> = [];
  projectRows.forEach((row, idx) => {
    row.project.milestones.forEach((m) => {
      const planned = m.planned_date ?? m.actual_date;
      if (!planned) return;
      milestonePoints.push([
        idx,
        dayjs(planned).valueOf(),
        m.milestone_name,
        m.status,
      ]);
    });
  });

  const renderItem = (_params: RenderApiParams, api: RenderApi) => {
    const yIdx = api.value(0) as number;
    const start = api.coord([api.value(1), yIdx]);
    const end = api.coord([api.value(2), yIdx]);
    const status = api.value(3) as string;
    const height = Math.max((api.size([0, 1])[1] as number) * 0.55, 12);

    const rectShape = {
      x: start[0],
      y: start[1] - height / 2,
      width: Math.max(end[0] - start[0], 2),
      height,
    };
    return {
      type: 'rect',
      shape: rectShape,
      style: api.style({ fill: STATUS_COLOR[status] ?? '#1F4E79' }),
    };
  };

  const option = {
    tooltip: {
      formatter: (p: { seriesType: string; data?: unknown[]; value: unknown[] }) => {
        if (p.seriesType === 'custom') {
          const [, startTs, endTs, status, name, code] = p.value as [
            number,
            number,
            number,
            string,
            string,
            string,
          ];
          const s = dayjs(startTs).format('YYYY-MM-DD');
          const e = dayjs(endTs).format('YYYY-MM-DD');
          return `<b>${name}</b><br>${code}<br>${STATUS_LABEL[status] ?? status}<br>${s} → ${e}`;
        }
        if (p.seriesType === 'scatter') {
          const [, ts, mname, mstatus] = p.value as [number, number, string, string];
          return `${dayjs(ts).format('YYYY-MM-DD')}<br>${mname} (${mstatus})`;
        }
        return '';
      },
    },
    grid: { left: 220, right: 40, top: 30, bottom: 40 },
    xAxis: {
      type: 'time',
      axisLabel: { formatter: '{yyyy}-{MM}' },
    },
    yAxis: {
      type: 'category',
      data: projectRows.map((r) => r.project.project_name),
      axisLabel: {
        formatter: (val: string) => (val.length > 22 ? val.slice(0, 22) + '…' : val),
      },
      inverse: true,
    },
    series: [
      {
        type: 'custom',
        renderItem,
        encode: { x: [1, 2], y: 0, tooltip: [4, 1, 2, 3] },
        data,
      },
      {
        type: 'scatter',
        symbol: 'diamond',
        symbolSize: 12,
        itemStyle: { color: '#F5222D' },
        encode: { x: 1, y: 0 },
        data: milestonePoints,
        z: 5,
      },
    ],
  };

  const onClick = (params: { dataIndex: number; seriesType: string; value?: unknown[] }) => {
    if (params.seriesType === 'custom' && Array.isArray(params.value)) {
      const code = params.value[5] as string;
      navigate(`/projects/${code}`);
    }
  };

  return (
    <Card
      title="项目甘特图"
      extra={
        <Tooltip title="◆ 红色菱形：里程碑（planned 优先；缺则 actual）">
          <Text type="secondary">点击项目条进入详情</Text>
        </Tooltip>
      }
    >
      <ReactECharts
        option={option}
        style={{ height: Math.max(220, projects.length * 38 + 80) }}
        onEvents={{ click: onClick }}
      />
      <div style={{ marginTop: 12 }}>
        {Object.entries(STATUS_LABEL).map(([k, v]) => (
          <Tag key={k} color={STATUS_COLOR[k]} style={{ marginRight: 8 }}>
            {v}
          </Tag>
        ))}
      </div>
    </Card>
  );
}
