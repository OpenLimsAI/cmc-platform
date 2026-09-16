import { useState } from 'react'
import { Alert, Checkbox, Collapse, Space, Table, Tabs } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import Plot from 'react-plotly.js'
import type { Data, Layout } from 'plotly.js'
import type { StabilityObservation, StabilityPanel, StabilitySeries } from '@/types/stability'

const present = (value: string | null) => value?.trim() ? value : '未提供'
const groupLabel = (series: StabilitySeries) => `${present(series.production_line_id)} / ${present(series.group_id)}`
export const stabilityGroupKey = (series: StabilitySeries) => JSON.stringify([series.production_line_id, series.group_id])
const number = (value: number | null | undefined) => value == null ? '—' : Number(value.toPrecision(6)).toString()
const observationColumns: ColumnsType<StabilityObservation> = [
  { title: '批号', dataIndex: 'batch_number', width: 170, render: (value) => <span style={{ whiteSpace: 'pre-wrap' }}>{present(value)}</span> },
  { title: '产线', dataIndex: 'production_line_id', width: 100, render: present },
  { title: '组别', dataIndex: 'group_id', width: 90, render: present },
  { title: '原始时间点', dataIndex: 'timepoint_raw', width: 110, render: present },
  { title: '原始数值', dataIndex: 'value_raw', width: 110, render: present },
  { title: '来源文本', dataIndex: 'value_str', width: 120, render: present },
  { title: '入图状态', width: 200, render: (_, row) => row.plottable ? '已纳入' : row.issues.join('；') },
  { title: '样品来源编号', dataIndex: 'sample_id', width: 150, render: present },
  { title: '检测来源编号', dataIndex: 'source_test_id', width: 150, render: present },
  { title: '结果来源编号', dataIndex: 'source_result_id', width: 150, render: present },
]

export default function StabilityChart({ panel, colors }: { panel: StabilityPanel; colors: Map<string, string> }) {
  const [view, setView] = useState('batch')
  const [showPoints, setShowPoints] = useState(true)
  const [showSd, setShowSd] = useState(true)
  const color = (series: StabilitySeries) => colors.get(stabilityGroupKey(series)) || '#748492'
  const fits: (StabilitySeries & { label: string })[] = view === 'batch-fit' ? panel.batches.map((series) => ({ ...series, label: `${present(series.batch_number)} · ${groupLabel(series)}` }))
    : panel.groups.map((series) => ({ ...series, label: groupLabel(series) }))
  let traces: Data[] = []
  if (view === 'batch') {
    traces = panel.batches.map((series, index) => ({
      type: 'scatter', mode: series.connect_points ? 'lines+markers' : 'markers', name: `${present(series.batch_number)} · ${groupLabel(series)}`,
      x: series.points.map((point) => point.timepoint), y: series.points.map((point) => point.value),
      connectgaps: false,
      line: { color: color(series), width: 1.5 }, marker: { color: color(series), size: 7, opacity: 0.8, line: {color:'#fff',width:1}, symbol: ['circle', 'square', 'diamond', 'triangle-up', 'cross'][index % 5] },
      customdata: series.points.map((point) => [point.sample_id, point.source_result_id]),
      hovertemplate: '时间点 %{x}<br>原值 %{y}<br>样品 %{customdata[0]}<br>结果 %{customdata[1]}<extra>%{fullData.name}</extra>',
    }))
  } else if (view === 'group') {
    traces = panel.groups.map((series) => ({
      type: 'scatter', mode: 'lines+markers', name: groupLabel(series),
      x: series.points.map((point) => point.timepoint), y: series.points.map((point) => point.mean),
      customdata: series.points.map((point) => [point.n, point.sd === null ? '不可计算' : number(point.sd)]),
      error_y: { type: 'data', array: series.points.map((point) => point.sd ?? 0), visible: showSd, color: color(series), thickness: 1.2, width: 2 },
      connectgaps: false, line: { color: color(series), width: 1.8 }, marker: { size: 6, color:color(series) },
      hovertemplate: '时间点 %{x}<br>均值 %{y}<br>N=%{customdata[0]}<br>样本SD %{customdata[1]}<extra>%{fullData.name}</extra>',
    }))
  } else {
    traces = fits.flatMap((series): Data[] => {
      const points = view === 'batch-fit'
        ? panel.batches.find(batch => batch.series_id === series.series_id)?.points || []
        : panel.batches.filter(batch => stabilityGroupKey(batch) === stabilityGroupKey(series)).flatMap(batch => batch.points)
      const fitted: Data[] = series.fit.available ? [{
        type: 'scatter', mode: 'lines', name: series.label, legendgroup:series.series_id, x: series.fit.x, y: series.fit.y,
        line: { color: color(series), width: 1.8 }, hovertemplate: '时间点 %{x}<br>拟合值 %{y}<extra>%{fullData.name}</extra>',
      }] : []
      if (showPoints) fitted.push({type:'scatter',mode:'markers',name:series.label,legendgroup:series.series_id,showlegend:!series.fit.available,
        x:points.map(point=>point.timepoint),y:points.map(point=>point.value),marker:{color:color(series),size:7,opacity:0.6},
        hovertemplate:'时间点 %{x}<br>原值 %{y}<extra>%{fullData.name}</extra>'})
      return fitted
    })
  }
  const layout: Partial<Layout> = {
    autosize: true, height: 430, paper_bgcolor: '#fff', plot_bgcolor: '#fff',
    font: { family: 'PingFang SC, Microsoft YaHei, Arial, sans-serif', size: 11, color: '#486073' },
    margin: { l: 65, r: 20, t: 20, b: 100 },
    xaxis: { title: { text: `时间点（${panel.timepoint_unit?.trim() ? panel.timepoint_unit : '单位未提供'}）` }, type: 'linear', gridcolor: '#e9eef2', automargin: true },
    yaxis: { title: { text: panel.unit?.trim() ? panel.unit : '原始数值（单位未提供）' }, gridcolor: '#e9eef2', automargin: true, zerolinecolor: '#dce4eb' },
    legend: { orientation: 'h', x: 0, y: -0.25, font: { size: 10 } }, hovermode: 'closest',
  }
  return <>
    {panel.plotted_n > 0 && panel.timepoint_count < 2 && <Alert type="info" showIcon className="qap-stability-warning"
      message={`这些记录只有一个时间点（${panel.observations.find((point) => point.plottable)?.timepoint_raw ?? '未提供'}），因此显示散点，无法形成随时间变化的曲线。`} />}
    {panel.warnings.map((warning) => <Alert key={warning} type="warning" showIcon message={warning} className="qap-stability-warning" />)}
    <Tabs activeKey={view} onChange={setView} items={[
      { key: 'batch', label: '逐批观察' },
      { key: 'group', label: '组均值 ± SD', disabled: !panel.statistics_available },
      { key: 'batch-fit', label: '逐批拟合', disabled: !panel.statistics_available },
      { key: 'group-fit', label: '组拟合', disabled: !panel.statistics_available },
    ]} />
    <Space className="qap-hint">
      {view === 'group' && <Checkbox checked={showSd} onChange={event=>setShowSd(event.target.checked)}>显示样本SD</Checkbox>}
      {view.includes('fit') && <Checkbox checked={showPoints} onChange={event=>setShowPoints(event.target.checked)}>显示原始观察点</Checkbox>}
    </Space>
    <div data-testid="stability-chart">
      {traces.length ? <Plot data={traces} layout={layout} style={{ width: '100%', height: 430 }} useResizeHandler
        config={{ displaylogo: false, responsive: true, toImageButtonOptions: { format: 'png', filename: 'stability_' + panel.attribute_name } }} />
        : <div className="qap-empty"><h3>{view.includes('fit') ? '当前记录不足以计算斜率' : '当前记录无法进入时间趋势图'}</h3><p>可在下方查看全部来源记录和具体原因。</p></div>}
    </div>
    {view === 'group' && <p className="qap-hint">按产线与组别，在每个时间点计算观察值均值和样本SD。N是观察数，未按批次加权；单点不绘制SD误差线。</p>}
    {view.includes('fit') && <><p className="qap-hint">带截距的线性拟合，仅描述当前观察范围；不外推有效期，不作显著性或等效判断。</p>
      <Table size="small" rowKey="series_id" pagination={{ pageSize: 10, hideOnSinglePage: true }} scroll={{ x: 650 }} dataSource={fits}
        columns={[
          { title: '系列', dataIndex: 'label', width: 240 },
          { title: 'N', render: (_, series) => series.fit.available ? series.fit.n : '—' },
          { title: '斜率（原始单位 / 时间单位）', render: (_, series) => series.fit.available ? number(series.fit.slope) : '—' },
          { title: '截距', render: (_, series) => series.fit.available ? number(series.fit.intercept) : '—' },
          { title: 'R²', render: (_, series) => series.fit.available ? number(series.fit.r_squared) : '—' },
          { title: '状态', render: (_, series) => series.fit.available ? '仅描述趋势' : series.fit.reason },
        ]} /></>}
    {panel.statistics_available && <Collapse className="qap-summary" items={[{key:'statistics',label:'查看各时间点统计（N / 均值 / SD / 最小 / 最大）',children:<>
      <p className="qap-hint">按产线、组别及时间点分别统计原始观察，不合并不同时间点。N为观察数，非独立批次数；单点SD为空。</p>
      <Table size="small" rowKey="key" pagination={{pageSize:10,hideOnSinglePage:true}} scroll={{x:720}}
        dataSource={panel.groups.flatMap(series=>series.points.map(point=>({...point,key:series.series_id+':'+point.timepoint,label:groupLabel(series)})))}
        columns={[{title:'产线 / 组别',dataIndex:'label',width:180},{title:'时间点',dataIndex:'timepoint'},{title:'N',dataIndex:'n'},
          {title:'均值',dataIndex:'mean',render:number},{title:'样本SD',dataIndex:'sd',render:number},
          {title:'最小值',dataIndex:'min',render:number},{title:'最大值',dataIndex:'max',render:number}]} />
    </>}]} />}
    <Collapse className="qap-summary" items={[{ key: 'records', label: `查看原始记录（${panel.n}条，入图${panel.plotted_n}条）`, children:
      <Table size="small" rowKey="observation_id" columns={observationColumns} dataSource={panel.observations}
        pagination={{ pageSize: 20, showSizeChanger: false, hideOnSinglePage: true }} scroll={{ x: 1450 }} /> }]} />
  </>
}
