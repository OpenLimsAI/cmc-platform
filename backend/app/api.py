import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from .config import Settings
from .domain import UTC, Snapshot, assess, current_view
from .inventory import load_tasks
from .security import authenticate
from .store import MemoryStore,PostgresStore


def public_snapshot(snap):
    payload=snap.model_dump(mode='json')
    # Server-only source locations and sender bindings must not become browser configuration.
    for item in payload['tasks']:
        task=item['task']
        for key in ('log_dir','log_pattern','backup_dir','backup_pattern','watermark_path','producer_users','jobs','ledger','db_source','instance'):
            task.pop(key,None)
    return payload

def create_app(settings=None,store=None):
    settings=settings or Settings();tasks=load_tasks(settings.inventory_path)
    if settings.component!='api':raise RuntimeError('API必须使用独立鉴权配置，不能以采集模式启动')
    store=store or (MemoryStore() if settings.mode=='demo' else PostgresStore(settings.database_url.get_secret_value()))
    @asynccontextmanager
    async def lifespan(app):
        try:await store.ping()
        except Exception:raise RuntimeError('监控存储不可用或迁移尚未完成') from None
        yield
        await store.close()
    app=FastAPI(title='数据中台运维',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.store=store;app.state.settings=settings
    async def guard(request:Request):
        value=request.headers.get('authorization','')
        token=value[7:] if value.startswith('Bearer ') else None
        actor=authenticate(token,settings);request.state.actor=actor;return actor
    @app.middleware('http')
    async def audit(request,call_next):
        rid=str(uuid4());request.state.request_id=rid
        try:response=await call_next(request)
        except Exception:
            response=JSONResponse({'message':'监控服务暂不可用，当前状态未核实','request_id':rid},503)
        if request.url.path.startswith('/api/v1/') and request.url.path!='/api/v1/health':
            route=request.scope.get('route');route_name=getattr(route,'path','unmatched')
            entry={'request_id':rid,'actor':getattr(request.state,'actor',None),'method':request.method,
                   'route':route_name,'result':response.status_code,'at':datetime.now(UTC).isoformat(),
                   'task_key':getattr(request.state,'task_key',None),'snapshot_id':getattr(request.state,'snapshot_id',None),
                   'returned_rows':getattr(request.state,'returned_rows',None),'range_days':getattr(request.state,'range_days',None)}
            try:await store.audit(entry)
            except Exception:
                # Fail closed, while retaining a bounded redacted refusal trail outside the database.
                try:
                    def fallback():
                        with settings.audit_fallback_path.open('a') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
                    await asyncio.to_thread(fallback)
                except Exception:pass
                response=JSONResponse({'message':'访问记录不可用，当前无法读取运维信息','request_id':rid},503)
        response.headers['X-Request-ID']=rid
        response.headers['Cache-Control']='no-store'
        return response
    @app.exception_handler(Exception)
    async def failure(request,exc):
        return JSONResponse({'message':'监控服务暂不可用，当前状态未核实','request_id':getattr(request.state,'request_id',None)},503)
    async def snapshot(request,sid=None):
        s=await store.latest(sid)
        if not s:
            if sid:raise HTTPException(410,'观测视图已过期或不存在，请重新打开')
            now=datetime.now(UTC)
            s=Snapshot(id='uncollected',collected_at=now,trigger='none',mode=settings.mode,
                       tasks=[assess(t,[],now,['尚未采集']) for t in tasks],gaps=['尚未取得任何有效采集'])
        request.state.snapshot_id=s.id
        if sid:return s
        view=current_view(s,datetime.now(UTC)).model_copy(deep=True)
        pending=await store.pending()
        if pending:
            view.gaps.append(f'{pending} 条更新请求尚未完成；以下为最后已知运行')
            for item in view.tasks:
                if item.task.enabled is not False:
                    item.state='unknown';item.label='更新待完成，当前未核实';item.collection_status='stale'
                    item.reasons=['更新请求尚未完成证据核对']
                    if item.last_run and item.last_run.status=='failed':item.reasons.insert(0,'最后已知失败，当前未核实')
        return view
    @app.get('/api/v1/health')
    async def health():return {'alive':True}
    @app.get('/api/v1/overview',dependencies=[Depends(guard)])
    async def overview(request:Request,snapshot_id:str|None=Query(None,max_length=36)):
        return public_snapshot(await snapshot(request,snapshot_id))
    @app.get('/api/v1/tasks',dependencies=[Depends(guard)])
    async def list_tasks(request:Request,snapshot_id:str|None=Query(None,max_length=36),kind:str|None=None,state:str|None=None,
                         q:str=Query('',max_length=100),offset:int=Query(0,ge=0,le=10000),limit:int=Query(100,ge=1,le=100)):
        data=public_snapshot(await snapshot(request,snapshot_id))
        rows=[x for x in data['tasks'] if (not kind or x['task']['kind']==kind) and (not state or x['state']==state) and q in x['task']['name']]
        request.state.returned_rows=len(rows[offset:offset+limit])
        return {'snapshot_id':data['id'],'items':rows[offset:offset+limit],'total':len(rows),'has_more':offset+limit<len(rows)}
    async def task_item(request,key,sid):
        if key not in {t.key for t in tasks}:raise HTTPException(404,'任务未登记')
        request.state.task_key=key
        data=public_snapshot(await snapshot(request,sid))
        return data,next(x for x in data['tasks'] if x['task']['key']==key)
    @app.get('/api/v1/tasks/{task_key}',dependencies=[Depends(guard)])
    async def detail(request:Request,task_key:str,snapshot_id:str|None=Query(None,max_length=36)):
        data,item=await task_item(request,task_key,snapshot_id)
        return {'snapshot_id':data['id'],'mode':data['mode'],'item':item}
    @app.get('/api/v1/tasks/{task_key}/runs',dependencies=[Depends(guard)])
    async def runs(request:Request,task_key:str,snapshot_id:str=Query(...,max_length=36),days:int=Query(7,ge=1,le=31),
                   offset:int=Query(0,ge=0,le=10000),limit:int=Query(100,ge=1,le=100)):
        data,_=await task_item(request,task_key,snapshot_id)
        cutoff=datetime.fromisoformat(data['collected_at'])
        rows,total=await store.history(task_key,cutoff-timedelta(days=days),cutoff+timedelta(microseconds=1),offset,limit)
        # Snapshot history is bounded by that snapshot's observation cutoff.
        result=[]
        for r in rows:
            copy=r.model_copy(deep=True)
            if copy.finish and copy.finish>cutoff:
                copy.finish=None;copy.status='running';copy.evidence=[];copy.children=[];copy.duration_seconds=None
                copy.integrity=None;copy.restore=None;copy.files=None;copy.size_bytes=None;copy.message='该观测时尚未完成'
            result.append(copy.model_dump(mode='json'))
        request.state.returned_rows=len(result);request.state.range_days=days
        return {'snapshot_id':data['id'],'items':result,'total':total,'has_more':offset+limit<total,'cutoff':data['collected_at']}
    @app.get('/api/v1/tasks/{task_key}/evidence',dependencies=[Depends(guard)])
    async def get_evidence(request:Request,task_key:str,evidence_id:str=Query(...,pattern=r'^[a-f0-9]{24}$'),snapshot_id:str=Query(...,max_length=36)):
        data,item=await task_item(request,task_key,snapshot_id)
        ev=next((e for e in (item['last_run'] or {}).get('evidence',[]) if e['id']==evidence_id),None)
        if not ev:raise HTTPException(404,'该观测中没有这条证据')
        return {'snapshot_id':data['id'],'evidence':ev}
    @app.post('/api/v1/refresh',dependencies=[Depends(guard)],status_code=202)
    async def refresh():
        if settings.mode=='demo':raise HTTPException(409,'模拟模式不读取真实来源')
        ident=await store.enqueue({'trigger':'manual'})
        return {'update_id':ident,'status':'pending'}
    @app.get('/api/v1/updates/{update_id}',dependencies=[Depends(guard)])
    async def update_status(update_id:str):
        if len(update_id)>240:raise HTTPException(404,'更新请求不存在')
        item=await store.get_update(update_id)
        if not item:raise HTTPException(404,'更新请求不存在')
        return {k:item[k] for k in ('id','status','snapshot_id')}
    return app
