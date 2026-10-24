import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Alert, Button, Form, InputNumber, Radio, Select, Slider, Spin, Table, Tag } from 'antd'
import axios from 'axios'
import { SidebarSlot } from '@/components/SidebarSlot'
import DataSourceSelect, { DataSourceNotice, sourceLabel } from '@/components/DataSourceSelect'
import SimilarityChart, { formatSimilarity } from '@/components/SimilarityChart'
import { api } from '@/services/api'
import { attributeLabel, indicatorGroups, selectPreset } from '@/services/releasePresentation'
import type { DataSource, ProjectMeta, ReleaseOptions } from '@/types'
import type { SimilarityPanel, SimilarityRequest } from '@/types/similarity'

const tier1Defaults = ['bioactivity_pct','bioactivity_ec50_ng_per_ml','binding_activity_pct','binding_activity_ec50_ng_per_ml']
const oldColumns = ['Project','Attribute','Tier_Level','Tier_Judgement','Reference','Test_Group','Brown-Forsythe p-value',
  'Levene p-value','TOST Method','Mean_Diff','ci_lower','ci_upper','Equivalent','Ref_Mean','Test_Mean',
  'Ref_Var','Test_Var','SE','DF','alpha','conf_level','pTOST']
const contextColumns = ['Delta','N_Ref','N_Test','Sample_Type','Test_Type','Method_Code','Unit','Placement_Status',
  'Sub_Lot','Calculation_Status','Calculation_Reason','Approval_Status']
const empty = (data_source:DataSource='RD',project_id=''):SimilarityRequest => ({data_source,project_id,sample_type:null,
  test_types:[],placement_statuses:[],batch_numbers:[],attribute_names:[],reference_lines:[],comparison_lines:[],reference_sd_multiplier:3,
  tier1_attribute_names:[...tier1Defaults],confidence_level:0.9,bf_threshold:0.05,tier2_hit_ratio:0.9,delta_mode:'auto',manual_delta:null})

export default function SimilarityPage() {
  const [draft,setDraft]=useState<SimilarityRequest>(()=>empty())
  const [projects,setProjects]=useState<ProjectMeta[]>([])
  const [options,setOptions]=useState<ReleaseOptions|null>(null)
  const [optionError,setOptionError]=useState<string|null>(null)
  const [projectError,setProjectError]=useState<string|null>(null)
  const [data,setData]=useState<SimilarityPanel[]|null>(null)
  const [applied,setApplied]=useState<SimilarityRequest|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [loading,setLoading]=useState(false)
  const [retry,setRetry]=useState(0)
  const [visible,setVisible]=useState(2)
  const [exporting,setExporting]=useState(false)
  const generation=useRef(0), active=useRef<AbortController|null>(null)
  const change=(next:SimilarityRequest)=>{ generation.current++; active.current?.abort(); setDraft(next);setData(null);setApplied(null);setError(null);setLoading(false);setVisible(2) }
  const patch=(value:Partial<SimilarityRequest>)=>change({...draft,...value})
  useEffect(()=>{
    const controller=new AbortController();setProjects([]);setProjectError(null)
    void api.projects(controller.signal,draft.data_source).then(result=>{if(!controller.signal.aborted)setProjects(result.data)})
      .catch(cause=>{if(!controller.signal.aborted)setProjectError(cause.message||'项目列表读取失败')})
    return ()=>controller.abort()
  },[draft.data_source,retry])
  useEffect(()=>{
    const controller=new AbortController();setOptions(null);setOptionError(null)
    if(draft.project_id) void api.releaseOptions(draft.project_id,controller.signal,draft.data_source).then(result=>{if(!controller.signal.aborted)setOptions(result.data)})
      .catch(cause=>{if(!controller.signal.aborted)setOptionError(cause.message||'选项读取失败')})
    return ()=>controller.abort()
  },[draft.project_id,draft.data_source,retry])
  const ready=!!options&&!!draft.project_id&&draft.reference_lines.length>0&&draft.comparison_lines.length>0&&draft.attribute_names.length>0&&
    (draft.delta_mode==='auto'||(draft.manual_delta!=null&&draft.manual_delta>0))
  const downloadReport=async()=>{
    if(!applied||!data)return
    setExporting(true)
    try {
      const response=await api.downloadSimilarityReport(applied)
      const url=URL.createObjectURL(response.data)
      const link=document.createElement('a');link.href=url;link.download=`${applied.project_id.replace(/[^\w-]/g,'_')}_相似性探索报告.xlsx`
      link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000)
    } catch(cause) {setError(cause instanceof Error?cause.message:'报告导出失败')}
    finally {setExporting(false)}
  }
  useEffect(()=>{
    const id=++generation.current;active.current?.abort();setData(null);setApplied(null);setError(null);setLoading(false)
    if(!ready)return
    const controller=new AbortController();active.current=controller;setLoading(true)
    const timer=window.setTimeout(()=>{
      void api.analyzeSimilarity(draft,controller.signal).then(result=>{if(id===generation.current){setData(result.data);setApplied(draft);setVisible(2)}})
        .catch(cause=>{if(id===generation.current&&!axios.isCancel(cause))setError(cause.message||'分析失败')})
        .finally(()=>{if(id===generation.current)setLoading(false)})
    },350)
    return ()=>{window.clearTimeout(timer);controller.abort();generation.current++}
  },[draft,ready,retry])
  const multi=(field:'test_types'|'placement_statuses'|'batch_numbers'|'reference_lines'|'comparison_lines'|'attribute_names'|'tier1_attribute_names',label:string,choices:string[])=> <Form.Item label={label} htmlFor={'similarity-'+field}>
    <Select id={'similarity-'+field} mode="multiple" allowClear showSearch maxTagCount={3} disabled={!options}
      value={field==='tier1_attribute_names'?draft[field].filter(value=>choices.includes(value)):draft[field]} placeholder="请选择"
      optionFilterProp="label" options={choices.map(value=>({value,label:field==='attribute_names'||field==='tier1_attribute_names'?attributeLabel(value,options?.attributes):value}))}
      onChange={values=>patch({[field]:values})} />
  </Form.Item>
  return <div className="qap-similarity">
    <SidebarSlot><details className="qap-filter-section" open><summary>相似性筛选<span>展开 / 收起</span></summary><div className="qap-filter-content"><Form layout="vertical" requiredMark={false}>
      <DataSourceSelect value={draft.data_source} onChange={source=>{setOptions(null);change(empty(source))}} />
      <Form.Item label="项目" htmlFor="similarity-project" extra="分析仅使用放行记录；括号为项目全部来源记录数">
        <Select id="similarity-project" showSearch allowClear value={draft.project_id||undefined} placeholder="选择项目" optionFilterProp="label"
          options={projects.map(project=>({value:project.project_id,label:`${project.project_id}（${project.n}条来源记录）`}))}
          onChange={project=>{setOptions(null);change(empty(draft.data_source,project||''))}} />
      </Form.Item>
      {(optionError||projectError)&&<Alert type="error" message={optionError||projectError} action={<Button onClick={()=>setRetry(value=>value+1)}>重试筛选</Button>} />}
      <Form.Item label="样品类型" htmlFor="similarity-sample"><Select id="similarity-sample" allowClear disabled={!options} placeholder="全部（分开展示）" value={draft.sample_type||undefined}
        options={(options?.sample_types||[]).map(value=>({value,label:value}))} onChange={value=>patch({sample_type:value??null})} /></Form.Item>
      {multi('test_types','检验类别（留空全部）',options?.test_types||[])}
      {draft.data_source==='EXCEL'&&multi('placement_statuses','放置状态（留空全部）',options?.placement_statuses||[])}
      {multi('batch_numbers','批号（留空全部）',options?.batch_numbers||[])}
      {multi('reference_lines','参比产线', (options?.production_line_ids||[]).filter(value=>!draft.comparison_lines.includes(value)))}
      {multi('comparison_lines','比较产线',(options?.production_line_ids||[]).filter(value=>!draft.reference_lines.includes(value)))}
      {multi('attribute_names','检测指标',options?.attributes.map(attr=>attr.attribute_name)||[])}
      {multi('tier1_attribute_names','Tier1 字段（自动 Δ=1.5×参比SD）',options?.attributes.map(attr=>attr.attribute_name)||[])}
      <h3 className="qap-sidebar-subheading">统计参数</h3>
      <Form.Item label="置信度（CI / TOST）" extra="新版按所选置信度正确计算：90% 对应单侧 α=0.05。">
        <Radio.Group value={draft.confidence_level} onChange={event=>patch({confidence_level:event.target.value})}>
          <Radio value={0.9}>90%</Radio><Radio value={0.95}>95%</Radio>
        </Radio.Group>
      </Form.Item>
      <Form.Item label="方差齐性阈值（Brown-Forsythe p）" extra="按该阈值实际选择合并方差或 Welch 公式。">
        <InputNumber min={0.001} max={0.5} step={0.001} precision={3} value={draft.bf_threshold} onChange={value=>{if(value!=null)patch({bf_threshold:value})}} />
      </Form.Item>
      <Form.Item label={`Tier2 命中比例阈值：${(draft.tier2_hit_ratio*100).toFixed(0)}%`}>
        <Slider min={0.5} max={1} step={0.01} value={draft.tier2_hit_ratio} onChange={value=>patch({tier2_hit_ratio:value})} />
      </Form.Item>
      <h3 className="qap-sidebar-subheading">Δ 策略</h3>
      <Form.Item label="Δ 获取方式" extra="旧版默认仅供探索，不代表已批准的质量标准。">
        <Radio.Group value={draft.delta_mode} onChange={event=>patch({delta_mode:event.target.value})}>
          <Radio value="auto">自动（按 Tier）</Radio><Radio value="manual">手动统一 Δ</Radio>
        </Radio.Group>
      </Form.Item>
      <Form.Item label="Tier2 的 k（自动 Δ=k×参比SD）" extra="自动模式的图5使用此倍数；手动模式的 Tier2 图5使用手动 Δ。">
        <InputNumber min={0.5} max={10} step={0.5} value={draft.reference_sd_multiplier} onChange={value=>{if(value!=null)patch({reference_sd_multiplier:value})}} />
      </Form.Item>
      <Form.Item label="手动统一 Δ" extra="仅手动模式生效；跨单位指标请分开分析。">
        <InputNumber min={0} step={0.1} value={draft.manual_delta} disabled={draft.delta_mode!=='manual'}
          placeholder="输入正数界值" onChange={value=>patch({manual_delta:value})} />
      </Form.Item>
      {draft.delta_mode==='manual'&&!(draft.manual_delta!=null&&draft.manual_delta>0)&&<Alert type="warning" showIcon message="请填写大于零的手动 Δ" style={{marginBottom:12}} />}
      <Button onClick={()=>change(empty(draft.data_source,draft.project_id))}>重置比较条件</Button>
      <h3 className="qap-sidebar-subheading">导出</h3>
      <Button onClick={downloadReport} disabled={!data||!data.length||!applied} loading={exporting}>下载 Excel 探索报告</Button>
      <p className="qap-hint">明确选择参比和比较产线后自动更新。不同样品、方法、单位和放置状态分开比较。Tier/等效结果仅供探索，不作批准判定。</p>
    </Form></div></details></SidebarSlot>
    <h1 className="qap-page-title">批次 / 场地相似性分析</h1>
    <p className="qap-page-description">沿用旧版两行三图与图后统一汇总表。图上 CI、±Δ 与探索性提示使用新版修正公式，不作质量放行判定。</p>
    <DataSourceNotice value={draft.data_source} />
    <section className="qap-presets"><h2 className="qap-section-heading">一键选择常用指标</h2><div className="qap-preset-grid">{indicatorGroups.map(group=>{
      const match=selectPreset(group.fields,options?.attributes||[])
      return <button type="button" className="qap-preset" key={group.label} aria-label={group.label} style={{'--preset-color':group.color} as CSSProperties}
        disabled={!options||!match.selected.length} onClick={()=>patch({attribute_names:match.selected})}><strong>{group.label.replace('_',' / ')}</strong><small>{match.selected.length} / {group.fields.length} 项可选</small></button>
    })}</div></section>
    <div className="qap-analysis-toolbar"><strong>统计图</strong><span role="status">{loading?'正在自动更新…':'选择后自动更新'}</span>{data&&<Tag>{data.length} 个条件 / 参比组合</Tag>}</div>
    {applied&&<div className="qap-applied"><span>{sourceLabel(applied.data_source)}</span><span>项目 {applied.project_id}</span><span>参比：{applied.reference_lines.join('、')}</span><span>比较：{applied.comparison_lines.join('、')}</span></div>}
    {error&&<Alert type="error" message={error} action={<Button onClick={()=>setRetry(value=>value+1)}>重试分析</Button>} />}
    {loading?<Spin tip="正在读取并比较…"><div style={{minHeight:240}} /></Spin>:data===null?<div className="qap-empty"><h3>选择项目、参比产线、比较产线及指标</h3><p>每个参比产线单独成图；不合并不同条件。参比及比较必须互不重叠。</p></div>:data.length===0?<div className="qap-empty">当前筛选没有可比较的放行记录，请调整条件。</div>:<>
      {data.slice(0,visible).map(panel=><section key={panel.panel_id} className="qap-attribute"><div className="qap-attribute-heading"><h2>{attributeLabel(panel.scope.attribute_name||'',options?.attributes)} — 参考组：{panel.reference.line}</h2></div>
        <div className="qap-applied">{[['sample_type','样品'],['test_type','类别'],['method_code','方法'],['unit','单位'],['placement_status','放置状态'],['sub_lot','子批号']].map(([field,label])=><span key={field}>{label}：{panel.scope[field]||'未提供'}</span>)}</div>
        <SimilarityChart panel={panel} confidenceLevel={applied?.confidence_level??draft.confidence_level}
          tier2Threshold={applied?.tier2_hit_ratio??draft.tier2_hit_ratio} /></section>)}
      {data.length>visible&&<div className="qap-load-more"><Button onClick={()=>setVisible(value=>value+2)}>再显示2组（{Math.min(visible,data.length)} / {data.length}）</Button></div>}
      <h2 className="qap-section-heading">统计汇总表</h2>
      <Alert type="warning" showIcon message="下列 Tier / Equivalent 是当前筛选参数下的探索性结果；参比资格及判定界值尚未经批准。" style={{marginBottom:12}} />
      <Table size="small" className="qap-similarity-report" rowKey="key" pagination={{pageSize:20,showSizeChanger:false}} scroll={{x:3600}}
        dataSource={data.flatMap(panel=>panel.comparisons.map(group=>({key:panel.panel_id+':'+group.line,...group.exploratory_statistics})))}
        columns={[...oldColumns,...contextColumns].map(column=>({title:column,dataIndex:column,key:column,
          render:(value:unknown)=>typeof value==='number'?formatSimilarity(value):value==null?'—':
            column==='Equivalent'&&value==='Not Equivalent'?'探索：未证实等效':
            column==='Equivalent'&&value==='Equivalent'?'探索：达到等效界值':
            column==='Tier_Judgement'&&value==='Not Similar'?'探索：未满足当前规则':
            column==='Tier_Judgement'&&value==='Similar'?'探索：满足当前规则':
            (column==='Tier_Judgement'||column==='Equivalent')?`探索：${value}`:String(value)}))} />
    </>}
    <p className="qap-method-note">按业务约定，数据源应只向看板提供 OOS/OOT 等调查完成后的最终有效结果；本页不处理调查过程。N 为纳入的结果行数。图1的等效提示为均值差检验；未通过 TOST 只表示未证实等效，不等于证实存在差异。Tier2 的图5命中标记为个体值范围法，使用与结果表相同的 Δ，但统计方法不同；未达命中阈值也不等于证实不相似。Tier1 的图5仅描述 k×SD 范围和比例，不显示判定符号。参比资格、单位及等效界值仍需确认；未执行LME或批准判定。</p>
  </div>
}
