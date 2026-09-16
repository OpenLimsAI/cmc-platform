import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Alert, Button, Form, InputNumber, Select, Spin, Tag } from 'antd'
import axios from 'axios'
import { SidebarSlot } from '@/components/SidebarSlot'
import DataSourceSelect, { DataSourceNotice, sourceLabel } from '@/components/DataSourceSelect'
import SimilarityChart from '@/components/SimilarityChart'
import { api } from '@/services/api'
import { attributeLabel, indicatorGroups, selectPreset } from '@/services/releasePresentation'
import type { DataSource, ProjectMeta, ReleaseOptions } from '@/types'
import type { SimilarityPanel, SimilarityRequest } from '@/types/similarity'

const empty = (data_source:DataSource='RD',project_id=''):SimilarityRequest => ({data_source,project_id,sample_type:null,
  test_types:[],placement_statuses:[],batch_numbers:[],attribute_names:[],reference_lines:[],comparison_lines:[],reference_sd_multiplier:3})

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
  const ready=!!options&&!!draft.project_id&&draft.reference_lines.length>0&&draft.comparison_lines.length>0&&draft.attribute_names.length>0
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
  const multi=(field:'test_types'|'placement_statuses'|'batch_numbers'|'reference_lines'|'comparison_lines'|'attribute_names',label:string,choices:string[])=> <Form.Item label={label} htmlFor={'similarity-'+field}>
    <Select id={'similarity-'+field} mode="multiple" allowClear showSearch maxTagCount={3} disabled={!options} value={draft[field]} placeholder="请选择"
      optionFilterProp="label" options={choices.map(value=>({value,label:field==='attribute_names'?attributeLabel(value,options?.attributes):value}))}
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
      <Form.Item label="探索参考带：均值 ± k×SD" extra="沿用旧版k=3作为展示起点；不是批准的等效界值。"><InputNumber min={0.5} max={10} step={0.5} value={draft.reference_sd_multiplier} onChange={value=>{if(value!=null)patch({reference_sd_multiplier:value})}} /></Form.Item>
      <Button onClick={()=>change(empty(draft.data_source,draft.project_id))}>重置比较条件</Button>
      <p className="qap-hint">明确选择参比和比较产线后自动更新。不同样品、方法、单位和放置状态分开比较，不按名称推断参比身份。</p>
    </Form></div></details></SidebarSlot>
    <h1 className="qap-page-title">批次 / 场地相似性分析</h1>
    <p className="qap-page-description">沿用旧版两行三图布局，先查看参比均值、差值与原始分布。当前为描述性比较，尚不判定等效性。</p>
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
        <SimilarityChart panel={panel} /></section>)}
      {data.length>visible&&<div className="qap-load-more"><Button onClick={()=>setVisible(value=>value+2)}>再显示2组（{Math.min(visible,data.length)} / {data.length}）</Button></div>}
    </>}
    <p className="qap-method-note">保留全部观察，重复批号不自动去重，N不代表独立批次数。参考带内比例仅描述当前原值分布，不表示Tier2通过。规格、单位、参比资格、重复结果取舍及等效界值须另行确认；未执行TOST、LME或批准判定。</p>
  </div>
}
