import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Alert, Button, Spin, Tag } from 'antd'
import axios from 'axios'
import { DataSourceNotice, sourceLabel } from '@/components/DataSourceSelect'
import { SidebarSlot } from '@/components/SidebarSlot'
import StabilityFilterPanel, { emptyStability } from '@/components/StabilityFilterPanel'
import StabilityChart, { stabilityGroupKey } from '@/components/StabilityChart'
import { api } from '@/services/api'
import { attributeLabel, indicatorGroups, selectPreset } from '@/services/releasePresentation'
import type { ProjectMeta } from '@/types'
import type { StabilityOptions, StabilityPanel, StabilityRequest } from '@/types/stability'

const describe = (items: string[], all: string) => items.length ? items.join('、') : all
const palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#d62728', '#8c564b', '#17becf', '#e377c2']
export default function StabilityPage() {
  const [draft, setDraft] = useState(() => emptyStability())
  const [projects, setProjects] = useState<ProjectMeta[]>([])
  const [projectError, setProjectError] = useState<string | null>(null)
  const [options, setOptions] = useState<StabilityOptions | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [retry, setRetry] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [panels, setPanels] = useState<StabilityPanel[] | null>(null)
  const [applied, setApplied] = useState<StabilityRequest | null>(null)
  const [visible, setVisible] = useState(4)
  const [preset, setPreset] = useState<string | null>(null)
  const analysis = useRef<AbortController | null>(null)
  const requestId = useRef(0)
  const resultsHeading = useRef<HTMLDivElement | null>(null)
  const scopeKey = JSON.stringify({ ...draft, attribute_names: [] })
  const colors = useMemo(() => new Map([...new Set((panels || []).flatMap((panel) => panel.batches.map(stabilityGroupKey)))].sort()
    .map((key, index) => [key, palette[index % palette.length]])), [panels])

  useEffect(() => {
    if (panels !== null && window.innerWidth < 1000) resultsHeading.current?.scrollIntoView({ block: 'start' })
  }, [panels])

  useEffect(() => {
    const controller = new AbortController()
    setProjectError(null); setProjects([])
    void api.projects(controller.signal, draft.data_source).then(({ data }) => { if (!controller.signal.aborted) setProjects(data) })
      .catch((cause) => { if (!controller.signal.aborted) setProjectError(cause instanceof Error ? cause.message : '项目列表读取失败') })
    return () => controller.abort()
  }, [retry, draft.data_source])
  useEffect(() => {
    const controller = new AbortController()
    const scope: StabilityRequest = JSON.parse(scopeKey)
    setOptions(null); setOptionsError(null)
    if (!scope.project_id) { setOptionsLoading(false); return () => controller.abort() }
    setOptionsLoading(true)
    void api.stabilityOptions(scope, controller.signal).then(({ data }) => { if (!controller.signal.aborted) setOptions(data) })
      .catch((cause) => { if (!controller.signal.aborted) setOptionsError(cause instanceof Error ? cause.message : '筛选项读取失败') })
      .finally(() => { if (!controller.signal.aborted) setOptionsLoading(false) })
    return () => controller.abort()
  }, [scopeKey, retry])
  useEffect(() => () => { requestId.current += 1; analysis.current?.abort() }, [])

  const change = (next: StabilityRequest) => {
    requestId.current += 1; analysis.current?.abort()
    if (next.data_source !== draft.data_source) { next = emptyStability('', next.data_source); setProjects([]); setProjectError(null) }
    if (JSON.stringify({ ...next, attribute_names: [] }) !== scopeKey) { setOptions(null); setOptionsLoading(Boolean(next.project_id)) }
    setDraft(next); setPanels(null); setApplied(null); setError(null); setLoading(false); setVisible(4); setPreset(null)
  }
  const run = async () => {
    if (!draft.project_id || !options || optionsLoading) return
    const id = ++requestId.current
    analysis.current?.abort()
    const controller = new AbortController()
    analysis.current = controller
    setLoading(true); setError(null); setPanels(null); setApplied(null)
    try {
      const result = await api.analyzeStability(draft, controller.signal)
      if (id === requestId.current) { setPanels(result.data); setApplied(draft); setVisible(4) }
    } catch (cause) {
      if (id === requestId.current && !axios.isCancel(cause)) setError(cause instanceof Error ? cause.message : '分析失败，请重试')
    } finally { if (id === requestId.current) setLoading(false) }
  }
  const chosen = indicatorGroups.find((group) => group.label === preset)
  const matched = chosen && options ? selectPreset(chosen.fields, options.attributes) : null
  return <div className="qap-stability">
    <SidebarSlot><StabilityFilterPanel value={draft} projects={projects} options={options} optionsLoading={optionsLoading} loading={loading}
      error={projectError || optionsError} onChange={change} onRun={() => void run()} onRetry={() => setRetry((value) => value + 1)} /></SidebarSlot>
    <h1 className="qap-page-title">稳定性趋势分析</h1>
    <p className="qap-page-description">沿时间点查看逐批变化，对照各组均值和趋势。不同样品、检验类别、方法与单位分开展示。</p>
    <DataSourceNotice value={draft.data_source} />
    <section className="qap-presets" aria-label="常用指标组合">
      <h2 className="qap-section-heading">一键选择常用指标</h2>
      {draft.data_source === 'QC' && <p className="qap-hint">QC 原始指标尚未匹配这些组合，请在筛选区选择「质量属性」，或留空查看全部。</p>}
      <div className="qap-preset-grid">{indicatorGroups.map((group) => {
        const match = selectPreset(group.fields, options?.attributes || [])
        return <button type="button" key={group.label} className="qap-preset" aria-label={group.label} aria-pressed={preset === group.label}
          style={{ '--preset-color': group.color } as CSSProperties} disabled={!options || !match.selected.length}
          onClick={() => { change({ ...draft, attribute_names: match.selected }); setPreset(group.label) }}>
          <strong>{group.label.replace('_', ' / ')}</strong><small>{options ? `${match.selected.length} / ${group.fields.length} 项可选` : '待选择项目'}</small>
        </button>
      })}</div>
      {matched && <div className="qap-preset-note">已选 {matched.selected.length} 项；未匹配 {matched.missing.length} 项。
        {matched.missing.length > 0 && <details><summary>查看未匹配项</summary>{matched.missing.map((name) => attributeLabel(name)).join('、')}</details>}</div>}
    </section>
    <div className="qap-analysis-toolbar" ref={resultsHeading}><strong>稳定性分析结果</strong>
      <Button type="primary" onClick={() => void run()} loading={loading} disabled={!draft.project_id || !options || optionsLoading}>生成图表</Button>
      {panels && <Tag>{panels.length} 个条件组合 · {panels.reduce((sum, panel) => sum + panel.n, 0)} 条观察</Tag>}</div>
    {applied && <div className="qap-applied" aria-label="本次稳定性条件">
      <span>{sourceLabel(applied.data_source)}</span><span>项目 {applied.project_id}</span><span>{describe(applied.sample_types, '全部样品')}</span><span>{describe(applied.test_types, '全部稳定性类别')}</span>
      <span>产线：{describe(applied.production_line_ids, '全部')}</span><span>组别：{describe(applied.group_ids, '全部')}</span><span>{applied.batch_numbers.length ? `已选 ${applied.batch_numbers.length} 个批号` : '全部稳定性批号'}</span>
    </div>}
    {error && <Alert type="error" message={error} showIcon action={<Button onClick={() => void run()}>重试分析</Button>} />}
    {loading ? <Spin tip="正在读取稳定性记录…"><div style={{ minHeight: 260 }} /></Spin> : panels === null ?
      <div className="qap-empty"><h3>{optionsLoading ? '正在读取稳定性筛选项…' : optionsError ? '筛选项读取失败，请重试' : !draft.project_id ? '从一个稳定性项目开始' : !options?.project_row_count ? '当前项目没有稳定性数值记录' : '筛选已就绪，点击「分析」'}</h3>
        <p>{draft.project_id ? '点击上方「生成图表」即可查看。可按样品、检验类别及批号缩小范围。' : `已读取 ${projects.length} 个有数值记录的项目。在页面上方或左侧的「稳定性筛选」中选择项目，再点击「生成图表」。`}</p></div>
      : panels.length === 0 ? <div className="qap-empty"><h3>当前条件下没有稳定性记录</h3><p>可减少筛选条件或切换项目。</p><Button style={{ marginTop: 16 }} onClick={() => change(emptyStability(draft.project_id, draft.data_source))}>清除筛选条件</Button></div>
      : <>{panels.slice(0, visible).map((panel) => <section className="qap-attribute" key={panel.panel_id}>
        <div className="qap-attribute-heading"><h2>{attributeLabel(panel.attribute_name, options?.attributes)}</h2><span className="qap-attribute-code">{panel.attribute_raw || panel.attribute_name}</span></div>
        <div className="qap-applied qap-stability-scope"><span>样品：{panel.sample_type || '未提供'}</span><span>类别：{panel.test_type || '未提供'}</span><span>方法：{panel.method_code || '未提供'}</span>
          <span>放置状态：{panel.placement_status || '未提供'}</span>{panel.sub_lot && <span>子批号：{panel.sub_lot}</span>}<span>结果单位：{panel.unit?.trim() ? panel.unit : '未提供'}</span><span>时间单位：{panel.timepoint_unit?.trim() ? panel.timepoint_unit : '未提供'}</span><span>{panel.n} 条观察 / {panel.timepoint_count} 个时间点</span></div>
        <StabilityChart panel={panel} colors={colors} />
      </section>)}{panels.length > visible && <div className="qap-load-more"><Button onClick={() => setVisible((count) => count + 4)}>再显示 4 项（当前 {Math.min(visible, panels.length)} / {panels.length}）</Button></div>}</>}
    <div className="qap-method-note">保留来源数值与时间单位；本轮不补入放行零点。研究编号与储存条件尚未接入，组统计只作当前筛选记录的描述。分类、单位、规格及来源批准状态仍待复核，不产生有效期或放行结论。</div>
  </div>
}
