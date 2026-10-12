import type {Task,Observation,Run,Snapshot,History,State,Kind} from './types'
const now=new Date();const base=new Date(now);base.setHours(7,0,0,0);if(base>now)base.setDate(base.getDate()-1)
const iso=(hours:number)=>new Date(base.getTime()-hours*3600000).toISOString()
const definitions:[string,string,Kind,string,string[],State,string][]=[
 ['lucullus','Lucullus 工艺数据','etl','rd-lucullus-etl',['01:00'],'warning','执行完成，有校验提醒'],
 ['rd-lims','研发 LIMS 数据','etl','rd-lims-etl',['08:00','12:00','16:00'],'success','执行成功'],
 ['qc-lims','QC LIMS 数据','etl','qc-lims-etl',['04:00'],'success','执行成功'],
 ['vicell','Vi-CELL 检测数据','etl','rd-vicell-etl',['12:05','16:20'],'success','执行成功'],
 ['nova','Nova 检测数据','etl','rd-nova-etl',['12:05','16:20'],'warning','执行完成，部分记录失败'],
 ['ingest-vicell','Vi-CELL 文件归档','backup','cmc-instrument-ingest',['02:00','11:45','16:00'],'success','文件归档完成，SHA256校验通过'],
 ['ingest-nova','Nova FLEX2 文件归档','backup','cmc-instrument-ingest',['02:00','11:45','16:00'],'success','检查完成，无需新增归档'],
 ['mdm-backup','MDM 数据库备份','backup','cmab-mdm-platform',['02:00'],'warning','备份完成，恢复未验证'],
 ['heartbeat-check','仪器心跳巡检','monitor','cmc-instrument-ingest',['09:00'],'success','检查完成'],
 ['training-sync','批号培训库同步','sync','rd-batch-registry',['00:00'],'success','同步完成'],
 ['biacore','Biacore 外部备份','backup','external',[],'unknown','尚未接入'],
 ['xevo','XEVO 外部备份','backup','external',[],'unknown','尚未接入'],
 ['empower','Empower 外部备份','backup','external',[],'unknown','尚未接入'],
 ['avant','AVANT 历史备份','backup','external',[],'unknown','尚未接入'],
 ['biacore-history','Biacore 历史目录','backup','external',[],'unknown','尚未接入'],
 ['retired-qc-lims','旧 QC ETL（已归档）','etl','qc_lims_etl',[],'disabled','已停用']]
function makeRun(key:string,state:State,index=0):Run{
 const finish=iso(2+24*index);const duration=key==='lucullus'?1120:60
 return {id:`demo:${key}:${index}`,task_key:key,start:new Date(new Date(finish).getTime()-duration*1000).toISOString(),finish,status:state==='failed'?'failed':key==='nova'?'partial_failed':'success',message:state==='failed'?'模拟：部分文件读取失败，请查看该次日志':'',duration_seconds:duration,rows:key.includes('lims')?12340:null,files:key==='ingest-nova'?0:key.startsWith('ingest')?128:key==='mdm-backup'?1:null,size_bytes:key==='mdm-backup'?1048576:null,children:[{name:'读取 / 归档',status:state==='failed'?'failed':key==='nova'?'partial_failed':'success'},{name:'写入 / 整理',status:state==='failed'?'unknown':'success'}],evidence:[{id:'a'.repeat(24),kind:'log',ref:'示例日志（模拟）',excerpt:state==='failed'?'[模拟] 开始任务\n[模拟] 读取失败，退出码 1\n[模拟] 本次执行失败':'[模拟] 开始任务\n[模拟] 必要步骤全部完成\n[模拟] 本次执行成功'}],integrity:key==='ingest-nova'?'no_changed_files':key.startsWith('ingest')?'scope_verified':null,restore:key.startsWith('ingest')?'not_applicable':null,archive_mode:index%2?'night':'day',source_kind:'demo'}
}
function nextSchedule(times:string[]):string{
 const next=times.map(t=>{const d=new Date(base);const [h,m]=t.split(':').map(Number);d.setHours(h,m,0,0);if(d<=base)d.setDate(d.getDate()+1);return d}).sort((a,b)=>a.getTime()-b.getTime())[0]
 return next.toISOString()
}
export function demoSnapshot():Snapshot{
 const observations:Observation[]=definitions.map(([key,name,kind,project,times,state,label])=>{
  const task:Task={key,name,kind,project,scope:'模拟 / 示例环境',archive_device:key==='ingest-vicell'?'vicell':key==='ingest-nova'?'flex2':null,enabled:state==='disabled'?false:state==='unknown'?null:true,times,timeout_minutes:30,notes:key==='biacore'?['备份方式（用户说明）：设备工作站自动备份到NAS，后续拟纳入cmc-instrument-ingest统一管理','具体计划与恢复证据尚未核实，集中接管未实施']:key.startsWith('ingest')?['按本设备同一次文件归档和SHA256核对判断']:kind==='backup'?['校验仅证明已有清单范围，未验证恢复能力']:[]}
  return {task,observed_at:base.toISOString(),collection_status:state==='unknown'?'unavailable':'ok',state,label,reasons:state==='failed'?['模拟失败，查看历史了解原因']:state==='warning'?['执行已完成，仍有校验或验证提醒']:[],last_run:['unknown','disabled'].includes(state)?null:makeRun(key,state),next_at:times.length?nextSchedule(times):null,gaps:state==='unknown'?['外部调度及开关尚未核实']:[]}
 })
 return {id:'demo-snapshot',collected_at:base.toISOString(),trigger:'daily_safety',tasks:observations,mode:'demo',gaps:['模拟数据不代表 Linux 当前运行状态','外部来源未全部接入'],inventory_version:'demo',rule_version:'v1'}
}
export function demoHistory(key:string,days=7,offset=0):History{
 const observation=demoSnapshot().tasks.find(x=>x.task.key===key)!
 return {snapshot_id:'demo-snapshot',items:observation.last_run?Array.from({length:days},(_,i)=>makeRun(key,i===3?'failed':observation.state,i)).slice(offset,offset+100):[],total:observation.last_run?days:0,has_more:false,cutoff:base.toISOString()}
}
