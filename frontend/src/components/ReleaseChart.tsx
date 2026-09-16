import Plot from 'react-plotly.js'
import type { Data, Layout, Shape, Annotations } from 'plotly.js'
import type { ReleaseAttribute } from '@/types'
import { releaseColors } from '@/services/releaseStyle'

export interface ChartDisplay { mean: boolean; sd: boolean; spec: boolean }
interface Props { attr: ReleaseAttribute; display: ChartDisplay; colors: Map<string | null, string> }
const groupLabel = (value: string | null) => value ?? '未填写组别'

export default function ReleaseChart({ attr, display, colors }: Props) {
  const groups = Array.from(new Set(attr.points.map((p) => p.group_id)))
  const batchOrder = Array.from(new Set(attr.points.map((point) => point.batch_number ?? '未填写批号')))
  const traces: Data[] = groups.map((group) => {
    const points = attr.points.filter((point) => point.group_id === group)
    return {
      type: 'scatter', mode: 'lines+markers', connectgaps: false, name: groupLabel(group),
      x: points.map((p) => p.batch_number ?? '未填写批号'), y: points.map((p) => p.value),
      line: { color: colors.get(group), width: 1.3 },
      marker: { size: 7, color: colors.get(group), opacity: 0.8, line: { color: '#fff', width: 1 } },
      hovertemplate: '批号 %{x}<br>原值 %{y}<extra>%{fullData.name}</extra>',
    }
  })
  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []
  const addLine = (y: number | null, color: string, dash: 'solid' | 'dash' | 'dot' = 'solid', label = '', width = 1) => {
    if (y == null || !Number.isFinite(y)) return
    if (label) annotations.push({ xref:'paper', x:1.01, yref:'y', y, text:label, showarrow:false, xanchor:'left', font:{color,size:10} })
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color, width, dash } })
  }
  if (display.spec) { addLine(attr.spec.lsl, releaseColors.spec, 'solid', '', 1.5); addLine(attr.spec.usl, releaseColors.spec, 'solid', '', 1.5) }
  if (display.mean) addLine(attr.sd_lines.mean, releaseColors.mean, 'solid', '参考均值', 2)
  if (display.sd) {
    addLine(attr.sd_lines.plus_1_5sd, releaseColors.sd15, 'dash', '+1.5 SD'); addLine(attr.sd_lines.minus_1_5sd, releaseColors.sd15, 'dash', '−1.5 SD')
    addLine(attr.sd_lines.plus_3sd, releaseColors.sd3, 'dash', '+3 SD'); addLine(attr.sd_lines.minus_3sd, releaseColors.sd3, 'dash', '−3 SD')
  }
  const extent = [...attr.points.map(p => p.value), ...shapes.map(s => Number(s.y0))].filter((v): v is number => v != null && Number.isFinite(v))
  const low = extent.length ? Math.min(...extent) : 0, high = extent.length ? Math.max(...extent) : 1
  const pad = (high - low || Math.abs(high) || 1) * 0.08
  const units = attr.units || []
  const unitLabel = units.length === 1 && units[0] ? units[0] : '原始数值'
  // Plotly mutates layout objects, so each chart owns its nested axis settings.
  const base = (): Partial<Layout> => ({
    height: 380, autosize: true, font: { family: 'PingFang SC, Microsoft YaHei, Arial, sans-serif', size: 11, color: '#486073' },
    margin: { l: 60, r: 16, t: 22, b: 105 }, paper_bgcolor: '#fff', plot_bgcolor: '#fff',
    yaxis: { title: { text: unitLabel, font: { size: 11 } }, gridcolor: '#e9eef2', zerolinecolor: '#dce4eb', automargin: true },
  })
  const config = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'] as ('lasso2d' | 'select2d')[] }
  return (
    <div className="qap-chart-pair">
      <div className="qap-chart" data-testid="release-trend-chart">
        <div className="qap-chart-label">批次趋势</div>
        <Plot data={traces} layout={{ ...base(), shapes, annotations, margin: {l:60,r:85,t:22,b:105}, yaxis:{ ...base().yaxis, range:[low-pad,high+pad] }, xaxis: { title: { text: '批号' }, type: 'category', categoryorder: 'array', categoryarray: batchOrder, tickangle: -45, automargin: true },
          legend: { orientation: 'h', y: 1.12, x: 0 }, showlegend: true }}
          config={{ ...config, toImageButtonOptions: { format: 'png', filename: attr.attribute_name + '_trend' } }} style={{ width: '100%', height: 380 }} useResizeHandler />
      </div>
      <div className="qap-chart" data-testid="release-group-chart">
        <div className="qap-chart-label">组别均值 ± 样本SD</div>
        {attr.statistics_available === false ? <div className="qap-empty">单位缺失，暂不计算</div> : <>
        <Plot data={[{
          type: 'bar', x: attr.groups.map((group) => groupLabel(group.group_id)), y: attr.groups.map((group) => group.mean),
          marker: { color: attr.groups.map((group) => colors.get(group.group_id) || releaseColors.trend) },
          error_y: { type: 'data', array: attr.groups.map((group) => group.sd ?? 0), visible: true, color: releaseColors.error, thickness: 1.2, width: 2 },
          text: attr.groups.map((group) => 'n=' + group.n), textposition: 'outside', cliponaxis: false,
          hovertemplate: '%{x}<br>均值 %{y}<br>%{text}<extra></extra>',
        }]} layout={{ ...base(), showlegend: false, margin: { l: 50, r: 16, t: 34, b: 105 },
          xaxis: { type: 'category', tickangle: -30, automargin: true }, bargap: 0.5 }}
          config={{ ...config, toImageButtonOptions: { format: 'png', filename: attr.attribute_name + '_groups' } }} style={{ width: '100%', height: 380 }} useResizeHandler /></>}
      </div>
    </div>
  )
}
