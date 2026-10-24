import React,{useEffect,useRef,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {QueryClient,QueryClientProvider,useQuery} from '@tanstack/react-query'
import {Alert,Button,Card,ConfigProvider,DatePicker,Drawer,Empty,Layout,Menu,Select,Space,Spin,Statistic,Table,Typography,message} from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import * as echarts from 'echarts'
import {api,query,loginRedirect} from './api'
import {filterFields,changeFilters,choices} from './filters'
import {getStoredToken,isTokenReadable,mdmLogout,startSessionGuard,TOKEN_CHANGED_EVENT} from './shared/cmabSession'
import {pageTitles,readPage,pageURL,type Section} from './navigation'
import {Overview} from './Overview'
import './style.css'
const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})
const titles=pageTitles
function Chart({items,filter}:any){
 const el=useRef<HTMLDivElement>(null)
 useEffect(()=>{if(!el.current)return;const chart=echarts.init(el.current)
 const plotted=items.filter((r:any)=>r.plot_status==='plotted')
 chart.setOption({tooltip:{renderMode:'richText',trigger:'item',formatter:(p:any)=>{const r=p.data.row;return `${r.sample_id}\n${r.display_value} ${r.source_unit}\n${r.trend_at}\n${r.trend_date_source}`}},grid:{left:70,right:35,bottom:60},legend:{data:['精确数值','删失结果（非实测值）']},xAxis:{type:'time',min:filter.date_from+'T00:00:00+08:00',max:filter.date_to+'T00:00:00+08:00'},yAxis:{type:'value',name:items[0]?.source_unit||'单位未确认',scale:true},dataZoom:[{type:'inside'},{type:'slider'}],series:[{name:'精确数值',type:'scatter',symbolSize:8,data:plotted.filter((r:any)=>r.result_kind==='exact_numeric').map((r:any)=>({value:[r.trend_at,Number(r.plot_value)],row:r}))},{name:'删失结果（非实测值）',type:'scatter',symbol:'triangle',symbolSize:11,itemStyle:{color:'#cf8d26'},data:plotted.filter((r:any)=>r.result_kind==='censored').map((r:any)=>({value:[r.trend_at,Number(r.plot_value)],row:r}))}]})
 const resize=()=>chart.resize();window.addEventListener('resize',resize);return()=>{window.removeEventListener('resize',resize);chart.dispose()}
 },[items,filter]);return <div ref={el} style={{height:400}}/>
}
function readLocationFilter(){const u=new URLSearchParams(location.search);const f:Record<string,any>={sample_status:['Reviewed']};for(const k of ['water_type','samplepoint_code','samplepoint_id','workitem_id','paramlist_id','paramlist_version_id','variant_id','param_id','unit','date_from','date_to'])if(u.has(k))f[k]=u.get(k);return f}
// Refreshing expiry alone must not recreate queries; identity/role changes must.
function authScope(token:string|null){try{const c=JSON.parse(atob((token||'').split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));return JSON.stringify([c.sub,c.roles,c.must_change_password])}catch{return ''}}
function App(){
 const [section,setSection]=useState<Section>(()=>readPage(location.pathname).section)
 const [removedNotice,setRemovedNotice]=useState(()=>readPage(location.pathname).removed)
 const [filter,setFilter]=useState<Record<string,any>>(()=>readPage(location.pathname).section==='trends'?readLocationFilter():{sample_status:['Reviewed']})
 const [group,setGroup]=useState<string>()
 const [trace,setTrace]=useState<any>(),[exporting,setExporting]=useState(false)
 const [exportFile,setExportFile]=useState<{url:string,name:string}>()
 const revision=useRef(0)
 useEffect(()=>{const restore=()=>{revision.current++;const page=readPage(location.pathname);setSection(page.section);setRemovedNotice(page.removed);if(page.section==='trends')setFilter(readLocationFilter());else history.replaceState(null,'',pageURL('overview'));setGroup(undefined);setExportFile(undefined);setTrace(undefined)};window.addEventListener('popstate',restore);return()=>window.removeEventListener('popstate',restore)},[])
 useEffect(()=>()=>{if(exportFile)URL.revokeObjectURL(exportFile.url)},[exportFile])
 const [tokenVersion,setTokenVersion]=useState(0)
 useEffect(()=>{if(!isTokenReadable(getStoredToken())){loginRedirect();return}let scope=authScope(getStoredToken());const update=()=>{const next=authScope(getStoredToken());if(next===scope)return;scope=next;revision.current++;client.clear();setExportFile(undefined);setTrace(undefined);setTokenVersion(v=>v+1)};window.addEventListener(TOKEN_CHANGED_EVENT,update);const stop=startSessionGuard({onLogout:()=>loginRedirect(),onTokenReplaced:update});return()=>{stop();window.removeEventListener(TOKEN_CHANGED_EVENT,update)}},[])
 const resolved=!!filter.date_from&&!!filter.date_to
 const context=useQuery({queryKey:['context',tokenVersion],queryFn:()=>api('context'),enabled:section==='trends'})
 const options=useQuery({queryKey:['filters',filter,tokenVersion],queryFn:()=>api('filters?'+query(filter)),enabled:resolved&&section==='trends'})
 useEffect(()=>{if(context.data&&(!filter.date_from||!filter.date_to)){const today=dayjs(context.data.current_date);setFilter(f=>({...f,date_from:f.date_from||today.subtract(12,'month').format('YYYY-MM-DD'),date_to:f.date_to||today.add(1,'day').format('YYYY-MM-DD')}))}},[context.data,filter.date_from,filter.date_to])
 useEffect(()=>{revision.current++;setExportFile(undefined);setTrace(undefined);setGroup(undefined);history.replaceState(null,'',pageURL(section,resolved?query(filter):''))},[filter,section])
 const comparison=useQuery({queryKey:['comparison-groups',filter,tokenVersion],queryFn:()=>api('comparison-groups?'+query(filter)),enabled:resolved&&section==='trends'})
 const trends=useQuery({queryKey:['trends',filter,group,tokenVersion],queryFn:()=>api('trends?'+query(filter)+'&comparison_group='+encodeURIComponent(group!)),enabled:resolved&&!!group&&section==='trends'})

 const update=(key:string,value:any)=>{if(key==='sample_status'&&!value.length){message.warning('请至少选择一种样品状态');return}setFilter(f=>changeFilters(f,{[key]:value}))}
 async function shortcut(months:number){try{const ctx=await api('context');client.setQueryData(['context',tokenVersion],ctx);const now=dayjs(ctx.current_date);setFilter(f=>changeFilters(f,{date_from:now.subtract(months,'month').format('YYYY-MM-DD'),date_to:now.add(1,'day').format('YYYY-MM-DD')}))}catch(e){message.error((e as Error).message)}}
 async function download(kind:string){if(!trends.data||!group)return;setExporting(true);const currentRevision=revision.current;try{const blob=await api('exports',{method:'POST',body:JSON.stringify({filter,comparison_group:group,export_kind:kind,context_id:trends.data.context_id,dataset_digest:trends.data.dataset_digest,chart_spec:{}})});if(currentRevision!==revision.current)return;const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='制药用水-'+kind+({chart:'.png',table:'.xlsx',bundle:'.zip'} as any)[kind];document.body.appendChild(a);a.click();a.remove();setExportFile({url,name:a.download})}catch(e){message.error((e as Error).message);client.invalidateQueries()}finally{setExporting(false)}}
 const columns=[{title:'样品',dataIndex:'sample_id',width:150},{title:'水类型',dataIndex:'water_type',width:100},{title:'水点编号',dataIndex:'samplepoint_code',width:120,render:(v:any)=>v||'未映射'},{title:'水点名称',dataIndex:'samplepoint_name',width:150},{title:'LIMS 点位内部 ID',dataIndex:'samplepoint_id',width:140,render:(v:any)=>v||'内部 ID 缺失'},{title:'方法 / 版本',width:220,render:(_:any,r:any)=>`${r.paramlistid||r.method||''} / ${r.paramlistversionid||r.version||''}`},{title:'参数',width:110,render:(_:any,r:any)=>r.paramid||r.parameter},{title:'原始结果',dataIndex:'display_value',width:140},{title:'绘图值',dataIndex:'plot_value',width:100},{title:'源单位',dataIndex:'source_unit',width:100},{title:'类别',dataIndex:'result_kind',width:130},{title:'趋势日期',dataIndex:'trend_at',width:210},{title:'日期来源',dataIndex:'trend_date_source',width:120},{title:'状态',dataIndex:'sample_status',width:110},{title:'来源',width:80,render:(_:any,r:any)=>r.result_id?<Button size="small" onClick={async()=>{try{setTrace(await api('results/trace?result_id='+encodeURIComponent(r.result_id)))}catch(e){message.error((e as Error).message)}}}>追溯</Button>:null}]
 return <Layout className="app"><Layout.Sider width={210} className="sidebar"><div className="brand">CMC<span>制药用水看板</span></div><Menu theme="dark" selectedKeys={[section]} items={Object.entries(titles).map(([key,label])=>({key,label}))} onClick={({key})=>{const next=key as Section;setRemovedNotice(false);setSection(next);history.pushState(null,'',pageURL(next,resolved?query(filter):''))}}/><div className="sider-note">QC LabVantage<br/>QC staging<br/>趋势核对</div></Layout.Sider><Layout><header><div><Typography.Title level={3}>{titles[section]||'总览'}</Typography.Title><span>纯化水 / 注射用水 / 纯蒸汽</span></div><Space><Button href="/">返回门户</Button><Button onClick={async()=>{await mdmLogout();loginRedirect()}}>退出</Button></Space></header><main>
 {removedNotice&&<Alert type="info" showIcon message="该功能已移除，已返回总览" closable onClose={()=>setRemovedNotice(false)}/>}
 {section==='overview'&&<Overview tokenVersion={tokenVersion}/>}
 {section==='trends'&&<>
 {context.error?<Alert type="error" message={(context.error as Error).message}/>:context.isPending?<Spin/>:null}
 <Card className="filters" title="取样点趋势筛选"><Space wrap>{filterFields.map(([k,label,col])=><Select key={k} aria-label={label} placeholder={label} showSearch optionFilterProp="label" allowClear value={filter[k]} style={{minWidth:130,maxWidth:260}} loading={options.isFetching} disabled={!resolved||options.isFetching||!!options.error} notFoundContent={options.isFetching?<Spin size="small"/>:'当前范围无可选项'} options={choices(options.data,k,col)} onChange={v=>update(k,v)}/>)}<Select aria-label="样品状态" mode="multiple" value={filter.sample_status} options={[{value:'Reviewed',label:'已复核'}]} disabled style={{minWidth:200}}/><DatePicker.RangePicker aria-label="日期范围" value={resolved?[dayjs(filter.date_from),dayjs(filter.date_to).subtract(1,'day')]:null} allowClear={false} onChange={v=>{if(v?.[0]&&v[1])setFilter(f=>changeFilters(f,{date_from:v[0]!.format('YYYY-MM-DD'),date_to:v[1]!.add(1,'day').format('YYYY-MM-DD')}))}}/>{[[3,'季度'],[6,'半年'],[12,'年度']].map(([n,label])=><Button key={n} onClick={()=>shortcut(Number(n))}>{label}趋势</Button>)}</Space>{options.error&&<Alert type="error" message={'筛选选项加载失败：'+(options.error as Error).message} action={<Button onClick={()=>options.refetch()}>重试</Button>}/>}<p className="muted">选项按日期、状态及前面的已选条件联动；修改上游会清空后续选择。起止日均包含；日期按 Asia/Shanghai。快捷范围从今天回溯 3 / 6 / 12 个日历月。</p></Card>
 {comparison.error&&<Alert type="error" message={(comparison.error as Error).message} action={<Button onClick={()=>comparison.refetch()}>重试</Button>}/>}
 {comparison.data&&<div className="metrics">{[['入选样品数','sample_count'],['方法数据集数','dataset_count'],['结果行数','result_count']].map(([label,k])=><Card key={k}><Statistic title={label} value={comparison.data.metrics[k]}/></Card>)}<Card><Statistic title="删失结果行" value={comparison.data.metrics.kinds.censored||0}/></Card></div>}

 {section==='trends'&&<Card title="单一比较组趋势" extra={context.data?.capabilities.export&&<Space>{[['chart','导出 PNG'],['table','导出 Excel'],['bundle','导出组合包']].map(([k,label])=><Button key={k} loading={exporting} disabled={!trends.data?.total} onClick={()=>download(k)}>{label}</Button>)}</Space>}>{exportFile&&<p><a href={exportFile.url} download={exportFile.name}>下载已生成文件：{exportFile.name}</a>（同一次取数；修改筛选后请重新生成）</p>}<Select aria-label="比较组" showSearch optionFilterProp="label" style={{width:'100%'}} placeholder="搜索并选择趋势指标，例如：电导率（方法 / 版本 / 单位分别展示）" value={group} onChange={value=>{revision.current++;setExportFile(undefined);setGroup(value)}} options={(comparison.data?.groups||[]).map((g:any)=>({value:g.id,label:`${g.label}（${g.count} 行）`}))}/>{trends.isFetching?<Spin/>:trends.error?<Alert type="error" message={(trends.error as Error).message}/>:trends.data?.total?<><Chart items={trends.data.items} filter={filter}/><p>未配置限度；图点 {trends.data.metrics.plot_count} 个 / 原始结果 {trends.data.total} 行。微生物限度 &lt;1 按 0 绘图，原文及阈值保留；删失结果不作为精确实测值。</p><Table rowKey="result_id" size="small" columns={columns} dataSource={trends.data.items} pagination={{pageSize:10}} scroll={{x:1800}}/></>:<Empty description={group?'当前条件无结果':'已筛选水点；请在上方选择趋势指标（如电导率），不同方法、版本和单位分别绘图'}/>}</Card>}
 </>}
 <Drawer title="完整来源追溯" width={720} open={!!trace} onClose={()=>setTrace(undefined)}>{trace?.gaps?.length>0&&<Alert type="warning" message={trace.gaps.join('；')}/>}<p>{trace?.association_note}</p><pre>{JSON.stringify(trace?.chain,null,2)}</pre></Drawer>
 </main></Layout></Layout>
}
createRoot(document.getElementById('root')!).render(<ConfigProvider locale={zhCN} theme={{token:{colorPrimary:'#167d9a',borderRadius:6}}}><QueryClientProvider client={client}><App/></QueryClientProvider></ConfigProvider>)
