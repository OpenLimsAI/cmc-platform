import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Alert, Button, Checkbox, Collapse, Space, Spin, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import axios from 'axios'
import FilterPanel from '@/components/FilterPanel'
import ReleaseChart, { type ChartDisplay } from '@/components/ReleaseChart'
import { DataSourceNotice, sourceLabel } from '@/components/DataSourceSelect'
import { SidebarSlot } from '@/components/SidebarSlot'
import { api } from '@/services/api'
import { attributeLabel, indicatorGroups, selectPreset } from '@/services/releasePresentation'
import { emptyDraft, readReleaseDraft, saveReleaseDraft } from '@/services/releaseDraft'
import { releaseColors } from '@/services/releaseStyle'
import type { ProjectMeta, ReleaseAttribute, ReleaseOptions, ReleaseRequest } from '@/types'

const fmt = (value: number | null | undefined, digits = 3) => value == null ? '—' : Number(value).toFixed(digits)

export default function ReleaseTrendPage() {
  const [draft, setDraft] = useState(readReleaseDraft)
  const [projects, setProjects] = useState<ProjectMeta[]>([])
  const [options, setOptions] = useState<ReleaseOptions | null>(null)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [retry, setRetry] = useState(0)
  const [preset, setPreset] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ReleaseAttribute[] | null>(null)
  const [applied, setApplied] = useState<ReleaseRequest | null>(null)
  const [rowCount, setRowCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(4)
  const [display, setDisplay] = useState<ChartDisplay>({ mean: true, sd: true, spec: false })
  const requestId = useRef(0)
  const analysisRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setProjectError(null); setProjects([])
    void api.projects(controller.signal, draft.data_source).then(({ data }) => {
      if (!controller.signal.aborted) setProjects(data)
    }).catch((cause) => {
      if (!controller.signal.aborted) setProjectError(cause instanceof Error ? cause.message : '项目列表读取失败')
    })
    return () => controller.abort()
  }, [retry, draft.data_source])

  useEffect(() => {
    const controller = new AbortController()
    setOptions(null)
    setOptionsError(null)
    if (!draft.project_id) { setOptionsLoading(false); return () => controller.abort() }
    setOptionsLoading(true)
    void api.releaseOptions(draft.project_id, controller.signal, draft.data_source).then(({ data }) => {
      if (!controller.signal.aborted) setOptions(data)
    }).catch((cause) => {
      if (!controller.signal.aborted) setOptionsError(cause instanceof Error ? cause.message : '项目筛选项读取失败')
    }).finally(() => { if (!controller.signal.aborted) setOptionsLoading(false) })
    return () => controller.abort()
  }, [draft.project_id, draft.data_source, retry])

  useEffect(() => () => { requestId.current += 1; analysisRequest.current?.abort() }, [])

  const change = (next: ReleaseRequest) => {
    requestId.current += 1
    analysisRequest.current?.abort()
    const changedSource = next.data_source !== draft.data_source
    const changedProject = changedSource || next.project_id !== draft.project_id
    const value = changedSource ? emptyDraft('', next.data_source) : changedProject ? emptyDraft(next.project_id, next.data_source) : next
    if (changedSource) { setProjects([]); setProjectError(null); setDisplay((current) => ({ ...current, spec: false })) }
    if (changedProject) { setOptions(null); setOptionsError(null) }
    setDraft(value)
    saveReleaseDraft(value)
    setData(null); setApplied(null); setError(null); setLoading(false); setVisibleCount(4)
    if (changedProject || JSON.stringify(value.attribute_names) !== JSON.stringify(draft.attribute_names)) setPreset(null)
  }

  const run = useCallback(async () => {
    if (!draft.project_id || !options || optionsLoading) return
    const id = ++requestId.current
    analysisRequest.current?.abort()
    const controller = new AbortController()
    analysisRequest.current = controller
    const request = { ...draft }
    setLoading(true); setError(null); setData(null); setApplied(null)
    try {
      const result = await api.analyzeRelease(request, controller.signal)
      if (id !== requestId.current) return
      setData(result.data); setApplied(request); setRowCount(Number(result.meta.row_count || 0)); setVisibleCount(4)
    } catch (cause) {
      if (id === requestId.current && !axios.isCancel(cause)) setError(cause instanceof Error ? cause.message : '分析未完成，请重试')
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [draft, options, optionsLoading])

  useEffect(() => {
    if (!draft.project_id || !options || optionsLoading) return
    setLoading(true)
    const timer = window.setTimeout(() => { void run() }, 350)
    return () => {
      window.clearTimeout(timer)
      requestId.current += 1
      analysisRequest.current?.abort()
    }
  }, [run, draft.project_id, options, optionsLoading])

  const colors = useMemo(() => {
    const groups = Array.from(new Set((data || []).flatMap((attr) => attr.points.map((point) => point.group_id))))
    groups.sort((a, b) => String(a ?? '').localeCompare(String(b ?? ''), 'zh'))
    return new Map(groups.map((group) => [group, releaseColors.trend]))
  }, [data])
  const selectedPreset = indicatorGroups.find((group) => group.label === preset)
  const presetSelection = selectedPreset && options ? selectPreset(selectedPreset.fields, options.attributes) : null
  const label = (name: string) => attributeLabel(name, options?.attributes || [])

  const columns: ColumnsType<ReleaseAttribute> = [
    { title: '质量属性', dataIndex: 'attribute_name', fixed: 'left', width: 190, render: label },
    ...(draft.data_source !== 'RD' ? [{ title: '单位 / 方法 / 样品 / 产线 / 放置状态', width: 250, render: (_: unknown, row: ReleaseAttribute) => [row.scope?.unit || '单位未提供', row.scope?.method_code || '方法未提供', row.scope?.sample_type || '样品未提供', row.scope?.production_line_id || '产线未提供', row.scope?.placement_status, row.scope?.sub_lot].join(' / ') }] : []),
    { title: 'N', dataIndex: 'n', width: 60 },
    { title: '均值', render: (_, row) => fmt(row.mean) },
    { title: '样本SD', render: (_, row) => fmt(row.sd_sample) },
    { title: '最小值', render: (_, row) => fmt(row.min) },
    { title: '最大值', render: (_, row) => fmt(row.max) },
    { title: 'RSD%', render: (_, row) => fmt(row.rsd_pct, 2) },
    { title: '旧配置下限', render: (_, row) => fmt(row.spec.lsl) },
    { title: '旧配置上限', render: (_, row) => fmt(row.spec.usl) },
    { title: '能力指数（待复核）', width: 160, render: (_, row) => row.capability.value == null ? '—' : row.capability.label + ' ' + fmt(row.capability.value, 2) },
  ]

  return (
    <div className="qap-release">
      <SidebarSlot><FilterPanel value={draft} projects={projects} options={options} optionsLoading={optionsLoading}
        projectError={projectError} optionsError={optionsError} onChange={change}
        onReset={() => change(emptyDraft(draft.project_id, draft.data_source))} onRetry={() => setRetry((value) => value + 1)} /></SidebarSlot>
      <h1 className="qap-page-title">放行数据趋势分析</h1>
      <p className="qap-page-description">按批次观察质量变化，对照各组均值与波动。选择项目、指标或调整筛选条件后，图表自动更新。</p>

      <DataSourceNotice value={draft.data_source} />
      <section className="qap-presets" aria-label="常用指标组合">
        <h2 className="qap-section-heading">一键选择常用指标</h2>
        {draft.data_source === 'QC' && <p className="qap-hint">QC 原始指标尚未匹配这些组合，请在筛选区选择「质量属性」，或留空查看全部。</p>}
        <div className="qap-preset-grid">
          {indicatorGroups.map((group) => {
            const match = selectPreset(group.fields, options?.attributes || [])
            return <button key={group.label} type="button" className="qap-preset" aria-pressed={preset === group.label}
              aria-label={group.label} style={{ '--preset-color': group.color } as CSSProperties}
              disabled={!options || match.selected.length === 0}
              title={!options ? '请先选择项目' : match.selected.length === 0 ? '当前项目没有准确匹配的指标；可从左侧手动选择' : '选择当前项目中准确匹配的指标'}
              onClick={() => { change({ ...draft, attribute_names: match.selected }); setPreset(group.label) }}>
              <strong>{group.label.replace('_', ' / ')}</strong>
              <small>{options ? match.selected.length + ' / ' + group.fields.length + ' 项可选' : '待选择项目'}</small>
            </button>
          })}
        </div>
        {presetSelection && <div className="qap-preset-note" role="status">
          已选 {presetSelection.selected.length} 项{presetSelection.missing.length > 0 && <>，另有 {presetSelection.missing.length} 项未匹配，未纳入本次选择。
            <details><summary>查看未匹配项</summary>{presetSelection.missing.map((name) => attributeLabel(name)).join('、')}</details></>}
        </div>}
      </section>

      <div className="qap-analysis-toolbar">
        <Space size={10} wrap><strong>数据分析结果</strong>{data && <Tag>{data.length} {draft.data_source !== 'RD' ? '个指标条件组合' : '个检测项'}</Tag>}
          <span className="qap-hint" role="status">{loading ? '正在自动更新…' : '按筛选条件自动更新'}</span>
        </Space>
        <Space wrap size={10}>
          <span className="qap-hint" style={{ margin: 0 }}>参考线</span>
          <Checkbox checked={display.mean} onChange={(e) => setDisplay({ ...display, mean: e.target.checked })}>均值</Checkbox>
          <Checkbox checked={display.sd} onChange={(e) => setDisplay({ ...display, sd: e.target.checked })}>±1.5 / 3 SD</Checkbox>
          <Checkbox disabled={draft.data_source !== 'RD'} checked={display.spec} onChange={(e) => setDisplay({ ...display, spec: e.target.checked })}>旧配置规格线</Checkbox>
        </Space>
      </div>
      {applied && <div className="qap-applied" aria-label="本次分析条件">
        <span>{sourceLabel(applied.data_source)}</span><span>项目 {applied.project_id}</span><span>{applied.sample_type || '全部样品类型'}</span><span>{rowCount} 条观察</span>
        {applied.production_line_ids?.length ? <span>产线：{applied.production_line_ids.join('、')}</span> : null}
        {applied.group_ids?.length ? <span>组别：{applied.group_ids.join('、')}</span> : null}
        {applied.batch_numbers?.length ? <span>已选 {applied.batch_numbers.length} 个批号</span> : null}
        {applied.test_types?.length ? <span>类别：{applied.test_types.join('、')}</span> : null}
        <span>批号年份：{[...(applied.batch_years || []).map(String), ...(applied.include_unknown_batch_year ? ['未识别'] : [])].join('、') || '全部'}</span>
      </div>}
      {error && <Alert type="error" showIcon message={error} action={<Button onClick={() => void run()}>重试分析</Button>} />}
      {loading ? <Spin tip="正在读取并分析…"><div style={{ minHeight: 260 }} /></Spin> : data === null ? (
        <div className="qap-empty"><h3>{optionsLoading ? '正在读取项目筛选项…' : optionsError ? '项目筛选项读取失败，请重试' : draft.project_id ? '准备自动生成图表…' : '从一个项目开始'}</h3>
          <p>{draft.project_id ? '常用指标可一键选择，也可以在数据筛选区挑选具体检测项，图表会自动更新。' : `已读取 ${projects.length} 个有数值记录的项目。在页面上方或左侧的「数据筛选」中选择项目即可自动生成图表。`}</p></div>
      ) : data.length === 0 ? (
        <div className="qap-empty"><h3>当前条件下没有放行数值结果</h3><p>请减少筛选条件或切换检测项。未匹配的指标不会自动替换成其他指标。</p><Button style={{ marginTop: 16 }} onClick={() => change(emptyDraft(draft.project_id, draft.data_source))}>清除筛选条件</Button></div>
      ) : <>
        {data.slice(0, visibleCount).map((attr) => <section className="qap-attribute" key={attr.panel_id || attr.attribute_name}>
          <div className="qap-attribute-heading"><h2>{label(attr.attribute_name)}</h2><span className="qap-attribute-code">{attr.attribute_name}</span></div>
          {(attr.units || []).length > 1 && <Alert type="warning" showIcon message={'该指标包含多种原始单位（' + attr.units.join('、') + '），统计口径尚待核对'} />}
          {attr.scope && <div className="qap-applied"><span>方法：{attr.scope.method_code || '未提供'}</span><span>样品：{attr.scope.sample_type || '未提供'}</span><span>类别：{attr.scope.test_type || '未提供'}</span><span>放置状态：{attr.scope.placement_status || '未提供'}</span>{attr.scope.sub_lot && <span>子批号：{attr.scope.sub_lot}</span>}<span>产线：{attr.scope.production_line_id || '未提供'}</span><span>单位：{attr.scope.unit?.trim() ? attr.scope.unit : '未提供'}</span></div>}
          {attr.statistics_available === false && <Alert type="info" message="单位缺失，仅展示原始观察，暂不计算组统计。" />}
          {attr.statistics_basis && <p className="qap-hint">统计按当前条件下的存储原值计算，未作百分比或单位换算；SD参考线不是质量标准。</p>}
          <ReleaseChart attr={attr} display={display} colors={colors} />
          {attr.reference_summary && <div className="qap-applied">
            <span>参考数据：{attr.reference_summary.mode === 'history' ? '历史年份' : '当前筛选'}</span>
            <span>年份：{attr.reference_summary.years.join('、') || '无可识别年份'}</span><span>N={attr.reference_summary.n}</span>
            <span>均值 {fmt(attr.reference_summary.mean)}</span><span>样本SD {fmt(attr.reference_summary.sd_sample)}</span>
            <span>最小 {fmt(attr.reference_summary.min)} / 最大 {fmt(attr.reference_summary.max)}</span><span>RSD {fmt(attr.reference_summary.rsd_pct,2)}%</span>
            {!attr.reference_summary.sd_available && <span>参考记录不足3条或数值不可计算，不绘制SD线</span>}
          </div>}
          {attr.legacy_spec_candidate && <details className="qap-spec-review"><summary>质量标准核对：旧配置原值（待确认）</summary>
            <p>来源：{attr.legacy_spec_candidate.source}；匹配：{attr.legacy_spec_candidate.origin || '未配置'}。</p>
            <p>下限：{fmt(attr.legacy_spec_candidate.lsl_raw)}；上限：{fmt(attr.legacy_spec_candidate.usl_raw)}。</p>
            <p>单位、适用版本和批准状态尚未核对；这些限度未画入图表，也未用于能力指数或合格判定。</p>
          </details>}

          {(display.mean || display.sd || display.spec) && <p className="qap-hint qap-reference-key">
            {display.mean && <span style={{ color: releaseColors.mean }}>灰实线：均值</span>}{display.sd && <><span style={{ color: releaseColors.sd15 }}>蓝虚线：±1.5 SD</span><span style={{ color: releaseColors.sd3 }}>红虚线：±3 SD</span></>}{display.spec && <span style={{ color: releaseColors.spec }}>红实线：旧配置规格</span>}
          </p>}
          <dl className="qap-stats-strip">{[
            ['观察数 N', attr.n], ['均值', fmt(attr.mean)], ['样本SD', fmt(attr.sd_sample)], ['最小值', fmt(attr.min)], ['最大值', fmt(attr.max)], ['RSD%', fmt(attr.rsd_pct, 2)],
          ].map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
        </section>)}
        {data.length > visibleCount && <div className="qap-load-more"><Button onClick={() => setVisibleCount((count) => count + 4)}>再显示 4 项（当前 {Math.min(visibleCount, data.length)} / {data.length}）</Button></div>}
        <Collapse className="qap-summary" items={[{ key: 'summary', label: (draft.data_source !== 'RD' ? '查看全部条件组合统计汇总（' : '查看全部检测项统计汇总（') + data.length + '项）',
          children: <><p className="qap-hint">{draft.data_source !== 'RD' ? 'QC 按原指标、方法、样品、类别、单位及来源产线标签分开统计；未匹配规格，不计算能力指数。' : '规格与能力指数沿用旧配置，尚未完成单位、规格版本及统计口径复核，不作为放行批准依据。'}</p><Table rowKey={(row) => row.panel_id || row.attribute_name} size="small" columns={columns} dataSource={data} pagination={false} scroll={{ x: 1040 }} /></> }]} />
      </>}
      <div className="qap-method-note">{draft.data_source !== 'RD' ? (draft.data_source === 'EXCEL' ? 'Excel 按相同检测项与条件保留原值统计。历史SD依据批号推算年份，不自动回退到当前数据；旧质量标准仅列出待核对，不产生放行批准。' : 'QC 保留来源字段和数值，产线/组别标签及分类语义尚待核对；有单位时显示描述统计，缺单位时只显示原始观察。不匹配规格，不产生放行批准。') : '当前均值与SD均来自本次筛选样本，历史年份参考区间尚未迁移。规格线默认隐藏；规格、单位及能力指数仍待复核，本页不产生放行批准。'}</div>
    </div>
  )
}
