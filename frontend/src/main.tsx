import React,{useEffect,useRef,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {QueryClient,QueryClientProvider,useQuery,useQueryClient} from '@tanstack/react-query'
import {demo,loadOverview,loadHistory,refreshOverview} from './api'
import {getStoredUser,getStoredToken,isTokenReadable,startSessionGuard,logoutToLogin} from './shared/cmabSession'
import type {Observation,Run,Kind,Snapshot} from './types'
import './style.css'
const kinds:Record<Kind,string>={etl:'ETL 数据同步',backup:'备份 / 归档',monitor:'巡检',sync:'培训同步'}
const symbol:Record<string,string>={success:'✓',failed:'!',warning:'!',unknown:'?',disabled:'−'}
const fmt=(value:string|null|undefined)=>value?new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Shanghai'}).format(new Date(value)):'尚无记录'
const duration=(seconds:number|null)=>seconds==null?'—':seconds<60?`${Math.round(seconds)} 秒`:`${Math.floor(seconds/60)} 分 ${Math.round(seconds%60)} 秒`
const runLabel:Record<string,string>={success:'执行成功',failed:'执行失败',partial_failed:'部分失败',running:'本次尚未完成',unknown:'未知'}
function Icon({kind}:{kind:Kind}){return <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">{kind==='backup'?<><path d="M4 8h20v15H4zM3 4h22v4H3zM10 13h8" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/></>:kind==='etl'?<><path d="M5 10h18l-4-4M23 18H5l4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/><path d="M23 10v3M5 18v-3" stroke="currentColor" strokeWidth="1.7"/></>:<><rect x="5" y="4" width="18" height="20" rx="3" stroke="currentColor" strokeWidth="1.7"/><path d="m9 14 3 3 7-7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></>}</svg>}
function useRoute(){
 const read=()=>location.pathname.match(/^\/ops\/tasks\/([a-z0-9_-]+)\/?$/)?.[1]||null
 const [key,setKey]=useState(read)
 useEffect(()=>{const f=()=>setKey(read());window.addEventListener('popstate',f);return()=>window.removeEventListener('popstate',f)},[])
 return {key,go:(value:string|null)=>{history.pushState({},'',value?'/ops/tasks/'+value:'/ops/');setKey(value);window.scrollTo(0,0)}}
}
function Card({item,onClick}:{item:Observation;onClick:()=>void}){
 const run=item.last_run
 return <button className={`task-card ${item.state}`} onClick={onClick} aria-label={`${item.task.name}，${item.label}，查看详情`}>
  <div className="card-top"><span className="task-icon"><Icon kind={item.task.kind}/></span><span className="kind">{kinds[item.task.kind]}</span><span className="open-icon" aria-hidden="true">↗</span></div>
  <h2>{item.task.name}</h2><div className="status-line"><span className="status-dot">{symbol[item.state]}</span><strong>{item.label}</strong></div>
  <p className="card-note">{item.reasons[0]||item.task.notes[0]||'查看逐次运行记录与证据'}</p>
  <dl className="card-facts"><div><dt>最近结束</dt><dd>{fmt(run?.finish)}</dd></div><div><dt>耗时</dt><dd>{duration(run?.duration_seconds??null)}</dd></div></dl>
  <div className="card-bottom"><span>{item.task.times.length?'每天 '+item.task.times.join(' / '):item.task.enabled===false?'已归档':'计划待核实'}</span><span>观测 {fmt(item.observed_at)}</span></div>
 </button>
}
function HistoryPanel({item,snapshot}:{item:Observation;snapshot:Snapshot}){
 const [days,setDays]=useState(7);const [offset,setOffset]=useState(0);const [selected,setSelected]=useState<Run|null>(null)
 const evidenceSection=useRef<HTMLElement>(null);const [selectionRequest,setSelectionRequest]=useState(0)
 function showRun(value:Run|null){setSelected(value);setSelectionRequest(n=>n+1)}
 useEffect(()=>{
  if(!selectionRequest)return
  evidenceSection.current?.focus({preventScroll:true})
  evidenceSection.current?.scrollIntoView({block:'start',behavior:'auto'})
 },[selectionRequest])
 const q=useQuery({queryKey:['history',item.task.key,snapshot.id,days,offset],queryFn:()=>loadHistory(item.task.key,snapshot.id,days,offset),retry:false,refetchOnWindowFocus:false})
 const run=selected||item.last_run
 return <>
  <section className="detail-section"><div className="section-heading"><h2>运行历史</h2><select aria-label="历史范围" value={days} onChange={e=>{setDays(Number(e.target.value));setOffset(0);setSelected(null)}}><option value={7}>最近7天</option><option value={31}>最近31天</option></select></div>
   {q.isLoading?<p>正在读取历史…</p>:q.error?<p className="error-text">历史读取失败，当前未核实：{q.error.message}</p>:!q.data?.items.length?<p className="empty">这段时间没有已取得的运行记录，不能据此判断全部正常。</p>:<div className="table-scroll"><table><thead><tr><th>计划 / 开始时间</th><th>结束时间</th><th>结果</th><th>耗时</th><th>证据</th></tr></thead><tbody>{q.data.items.map(r=><tr key={r.id} className={selected?.id===r.id?'selected':''}><td>{r.source_kind==='schedule'?'计划 ':''}{fmt(r.start)}</td><td>{fmt(r.finish)}</td><td><span className={`run-status ${r.status==='failed'?'failed':r.status==='success'?'success':'warning'}`}>{r.source_kind==='schedule'?'未按计划启动':runLabel[r.status]||r.status}</span></td><td>{duration(r.duration_seconds)}</td><td><button className="text-button" onClick={()=>showRun(r)} aria-label={`查看${fmt(r.start)}的证据`}>查看记录</button></td></tr>)}</tbody></table></div>}
   {q.data&&<div className="pagination"><span>已取得 {q.data.total} 次记录 · 截至 {fmt(q.data.cutoff)}</span><div><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-100))}>上一页</button><button disabled={!q.data.has_more} onClick={()=>setOffset(offset+100)}>下一页</button></div></div>}
  </section>
  <section className="detail-section run-evidence" ref={evidenceSection} tabIndex={-1} aria-labelledby="run-evidence-title"><div className="section-heading"><h2 id="run-evidence-title">{selected?'所选运行的步骤与证据':'最近运行的步骤与证据'}</h2>{selected&&<button className="text-button" onClick={()=>showRun(null)}>回到最近运行</button>}</div>
   {run?<><p className="section-subtitle">{fmt(run.start)} · {run.source_kind==='schedule'?'未按计划启动':runLabel[run.status]||run.status} · {duration(run.duration_seconds)}</p>{run.message&&<p className="inline-note">{run.message}</p>}
    <div className="steps">{run.children.map((child,i)=><div key={i}><span className={`step-symbol ${child.status==='success'?'success':child.status==='failed'?'failed':'unknown'}`}>{child.status==='success'?'✓':child.status==='failed'?'!':'?'}</span><span>{child.name}</span><small>{runLabel[child.status]||child.status}</small></div>)}</div>
    {run.evidence.length?run.evidence.map((e,i)=><details key={`${run.id}:${selectionRequest}:${e.id}`} className="evidence" open={selectionRequest>0&&i===0}><summary>{e.ref}<span>{e.kind==='log'||e.kind==='journal'?'脱敏日志':'来源摘要'}</span></summary><pre>{e.excerpt}</pre></details>):<p className="empty">这次运行没有已取得的证据摘要。</p>}
   </>:<p className="empty">尚无可关联的运行证据。</p>}
  </section>
 </>
}
function Detail({item,snapshot,back}:{item:Observation;snapshot:Snapshot;back:()=>void}){
 const run=item.last_run
 return <><button className="back-button" onClick={back}>← 返回任务看板</button><div className="detail-heading"><div><p className="eyebrow">{kinds[item.task.kind]} / {item.task.project}</p><h1>{item.task.name}</h1></div><span className={`detail-status ${item.state}`}>{symbol[item.state]} {item.label}</span></div>
  <section className="detail-overview"><div><span>最近结束</span><strong>{fmt(run?.finish)}</strong></div><div><span>本次耗时</span><strong>{duration(run?.duration_seconds??null)}</strong></div><div><span>每天计划</span><strong>{item.task.times.join(' / ')||'尚未核实'}</strong></div><div><span>下一次计划</span><strong>{fmt(item.next_at)}</strong></div></section>
  {(item.reasons.length>0||item.gaps.length>0)&&<div className="notice"><strong>需要关注</strong><p>{[...new Set([...item.reasons,...item.gaps])].join('；')}</p></div>}
  {item.task.kind==='backup'&&<section className="detail-section"><h2>备份证据</h2><div className="backup-grid"><div><span>执行结果</span><strong>{run?runLabel[run.status]:'未核实'}</strong></div><div><span>备份产物</span><strong>{run?.files!=null?`${run.files} 个文件`:'清单未取得'}</strong><small>{run?.size_bytes!=null?`${(run.size_bytes/1048576).toFixed(2)} MB`:''}</small></div><div><span>完整性检查</span><strong>{run?.integrity==='verified'?'已验证':run?.integrity==='scope_verified'?'仅清单范围':run?.integrity==='failed'?'验证失败':run?.integrity==='unknown'?'结果未知':'未验证'}</strong></div><div><span>恢复验证</span><strong>{run?.restore==='verified'?'实际恢复通过':run?.restore==='failed'?'恢复失败':run?.restore==='unknown'?'结果未知':run?.verification?.status==='incomplete'?'验证未完成':run?.verification&&['pending','running'].includes(run.verification.status)?'验证尚未完成':'未找到执行记录'}</strong></div></div>{run?.verification&&<><p className="section-subtitle">验证结论：{run.verification.reason||'当前未知'} · 验证结束：{fmt(run.verification.finished_at)}{run.verification.target_pg_version?` · PostgreSQL ${run.verification.target_pg_version}`:''}</p>{run.verification.artifact&&<p className="section-subtitle">对应备份：{run.verification.artifact}</p>}{run.verification.cleanup_status==='failed'&&<p className="inline-note">临时环境清理失败，需要检查服务器残留资源。</p>}</>}<p className="section-subtitle">这里展示已有验证证据；MDM验证范围为数据库结构和数据，不包含整站业务功能、数据库账号权限或异地灾备。</p></section>}
  <HistoryPanel key={item.task.key+snapshot.id} item={item} snapshot={snapshot}/><section className="detail-section"><h2>任务说明</h2><p>{item.task.scope} · 最近观测 {fmt(item.observed_at)}</p>{item.task.notes.map((x,i)=><p className="section-subtitle" key={i}>{x}</p>)}</section>
 </>
}
function App(){
 const client=useQueryClient();const route=useRoute();const [kind,setKind]=useState('all');const [onlyAbnormal,setOnlyAbnormal]=useState(false);const [search,setSearch]=useState('');const [refreshing,setRefreshing]=useState(false);const [refreshError,setRefreshError]=useState('')
 const user=getStoredUser();const allowed=demo||Boolean(user?.roles?.includes('SYS_ADMIN')&&!user.must_change_password)
 useEffect(()=>{if(demo)return;if(!getStoredToken()||!isTokenReadable(getStoredToken())){location.assign('/login?redirect='+encodeURIComponent(location.pathname));return}return startSessionGuard({onLogout:logoutToLogin('/login?redirect=%2Fops%2F')})},[])
 const q=useQuery({queryKey:['overview'],queryFn:loadOverview,enabled:allowed,retry:false,staleTime:Infinity,refetchOnWindowFocus:false})
 async function update(){setRefreshing(true);setRefreshError('');try{client.setQueryData(['overview'],await refreshOverview())}catch(e){setRefreshError(e instanceof Error?e.message:'更新失败，当前状态未核实')}finally{setRefreshing(false)}}
 const data=q.data;const error=refreshError||q.error?.message||''
 const items=data?.tasks.map(item=>error?{...item,state:'unknown' as const,label:'当前未知',reasons:['更新失败；以下运行仅为最后已知结果']}:item)||[]
 const active=items.filter(t=>t.task.enabled!==false&&t.task.project!=='external')
 const external=items.filter(t=>t.task.enabled!==false&&t.task.project==='external')
 const retired=items.filter(t=>t.task.enabled===false)
 const abnormal=active.filter(t=>['failed','warning','unknown'].includes(t.state))
 const selected=items.find(i=>i.task.key===route.key)
 const rank:Record<string,number>={failed:0,warning:1,unknown:2,success:3,disabled:4}
 const filterTasks=(tasks:Observation[])=>tasks.filter(i=>(kind==='all'||(kind==='other'?['monitor','sync'].includes(i.task.kind):i.task.kind===kind))&&(!onlyAbnormal||['failed','warning','unknown'].includes(i.state))&&i.task.name.toLowerCase().includes(search.toLowerCase())).sort((a,b)=>(a.state==='unknown'&&a.last_run?.status==='failed'?0.5:rank[a.state])-(b.state==='unknown'&&b.last_run?.status==='failed'?0.5:rank[b.state]))
 const visible=filterTasks(active)
 const externalVisible=filterTasks(external)
 const retiredVisible=filterTasks(retired)
 return <><header className="topbar"><a href={demo?'/ops/':'/'} className="brand"><span className="brand-mark">CMAB</span><span>数据中台运维</span></a><div className="topbar-right"><span>{demo?'界面预览':user?.full_name||'管理员'}</span>{!demo&&<a href="/">返回门户</a>}</div></header>
  {demo&&<div className="demo-banner"><strong>模拟数据</strong><span>用于界面与功能验证，不代表 Linux 当前状态，不读取或执行真实任务。</span></div>}
  <main>{!allowed?<section className="access-panel"><h1>仅系统管理员可进入</h1><p>{user?.must_change_password?'请先到MDM修改临时密码。':'请使用具有 MDM SYS_ADMIN 角色的账号访问。'}</p><a href="/">返回门户</a></section>:<>
  {error&&<div className="error-banner" role="alert"><strong>更新异常，当前状态未核实</strong><span>{error}</span><button onClick={update} disabled={refreshing}>重试更新</button></div>}
  {q.isLoading?<div className="loading">正在读取最近观测…</div>:data?<>
   {route.key?selected?<Detail item={selected} snapshot={data} back={()=>route.go(null)}/>:<div className="access-panel"><h1>任务未登记</h1><button onClick={()=>route.go(null)}>返回看板</button></div>:<>
   <div className="page-heading"><div><p className="eyebrow">Linux 数据中台 · 只读监控</p><h1>任务看板</h1><p className="subtitle">每个任务的最近结果，以及需要你关注的问题。</p></div><div className="heading-actions"><span>最近汇总<br/><strong>{data.trigger==='none'?'尚未采集':fmt(data.collected_at)}</strong><small>北京时间 · 每天07:00兜底</small></span><button className="primary-button" onClick={update} disabled={refreshing}>{refreshing?'更新中…':'更新状态'}</button></div></div>
   <section className="attention"><div className="attention-title"><span className="attention-icon">!</span><div><strong>{abnormal.length?`${abnormal.length} 个Linux任务需要关注`:'Linux在用任务无已确认异常'}</strong><p>{active.filter(x=>x.state==='failed').length} 个执行异常 · {active.filter(x=>x.state==='warning').length} 个提醒 · {active.filter(x=>x.state==='unknown').length} 个未知</p></div></div><button onClick={()=>setOnlyAbnormal(!onlyAbnormal)}>{onlyAbnormal?'查看全部任务':'只看需要关注的任务'}</button></section>
   <div className="toolbar"><div className="tabs" role="group" aria-label="任务类型">{[['all','全部任务'],['etl','ETL'],['backup','备份 / 归档'],['other','其他运维']].map(([value,label])=><button key={value} className={kind===value?'active':''} onClick={()=>setKind(value)}>{label}</button>)}</div><label className="search"><span aria-hidden="true">⌕</span><input aria-label="搜索任务名称" value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索任务名称"/></label></div>
   <section className="task-grid" aria-label="Linux在用任务卡片">{visible.map(item=><Card key={item.task.key} item={item} onClick={()=>route.go(item.task.key)}/>)}</section>{visible.length===0&&<div className="empty">没有符合筛选条件的任务。</div>}
   {external.length>0&&<details className="secondary-tasks"><summary><span>外部备份与接入缺口</span><span className="group-count">{external.length} 项 · 尚未接入</span></summary><div className="secondary-body"><p className="section-subtitle">这些来源未计入上方Linux任务关注数；备份计划、执行结果及恢复证据仍需核实。</p><section className="task-grid" aria-label="外部备份卡片">{externalVisible.map(item=><Card key={item.task.key} item={item} onClick={()=>route.go(item.task.key)}/>)}</section>{externalVisible.length===0&&<p className="empty">没有符合筛选条件的外部备份。</p>}</div></details>}
   {retired.length>0&&<details className="secondary-tasks"><summary><span>已停用任务</span><span className="group-count">{retired.length} 项 · 保留历史</span></summary><div className="secondary-body"><p className="section-subtitle">已停用任务不计入在用任务关注数，可查看已有历史和证据。</p><section className="task-grid" aria-label="已停用任务卡片">{retiredVisible.map(item=><Card key={item.task.key} item={item} onClick={()=>route.go(item.task.key)}/>)}</section>{retiredVisible.length===0&&<p className="empty">没有符合筛选条件的已停用任务。</p>}</div></details>}
   <div className="coverage"><strong>覆盖与证据说明</strong>{data.gaps.map((gap,i)=><p key={i}>{gap}</p>)}<p>绿色表示本次执行有成功证据；备份完整性与恢复能力在详情中分别说明。</p></div>
   </>}
  </>:<section className="access-panel"><h1>尚未取得监控观测</h1><p>无法确认当前运行情况。</p><button onClick={update}>尝试更新</button></section>}
  </>}</main><footer>数据中台运维 · 执行结果与证据可追溯 · V1 只读</footer></>
}
const client=new QueryClient({defaultOptions:{queries:{refetchOnWindowFocus:false,refetchOnReconnect:false,retry:false}}})
const reactRoot=import.meta.hot?.data.reactRoot||createRoot(document.getElementById('root')!)
if(import.meta.hot)import.meta.hot.data.reactRoot=reactRoot
reactRoot.render(<React.StrictMode><QueryClientProvider client={client}><App/></QueryClientProvider></React.StrictMode>)
