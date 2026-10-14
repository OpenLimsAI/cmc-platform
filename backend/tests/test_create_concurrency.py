"""只连 cmab_test；覆盖重试竞争、真实提交与记录结果的事务边界。"""
import asyncio
import json
import os
from uuid import UUID, uuid4

import pytest
import redis.asyncio as redis_async
from app.core.config import settings
from app.core.exceptions import DuplicateRequestError
from app.domains.ars.schemas import AssetCreate
from app.domains.ars.services import AssetService
from app.domains.auth.models import User
from app.domains.eqp.schemas import EquipmentCreate
from app.domains.eqp.services import EquipmentService
from app.domains.mm.schemas import MaterialCreate
from app.domains.mm.services import MaterialService
from app.domains.prs.schemas import ProjectCreate
from app.domains.prs.services import ProjectService
from app.domains.srs.schemas import SubstanceCreate
from app.domains.srs.services import SubstanceService
from app.domains.target.schemas import TargetCreate
from app.domains.target.services import TargetService
from app.shared import idempotency
from app.shared.idempotency import (
    IdempotencyService,
    IdempotencyUnavailableError,
    _canonical_body_hash,
)
from app.shared.idempotency_models import IdempotencyResult
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DOMAINS = {
    'substances': (SubstanceService, SubstanceCreate, {'substance_type':'mab','preferred_name':'重复提交物质'}, 'srs','substance'),
    'projects': (ProjectService, ProjectCreate, {'project_type':'cmc','project_name':'重复提交项目'}, 'prs','project'),
    'assets': (AssetService, AssetCreate, {'asset_type':'mab','internal_name':'重复提交资产'}, 'ars','asset'),
    'materials': (MaterialService, MaterialCreate, {'material_type':'reagent','material_name':'重复提交物料'}, 'mm','material'),
    'equipments': (EquipmentService, EquipmentCreate, {'category':'通用实验室设备','equipment_name':'重复提交设备'}, 'eqp','equipment'),
    'targets': (TargetService, TargetCreate, {'target_name':'重复提交靶点'}, 'tgt','target'),
}


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get('TEST_DB') == 'cmab_test'
    assert settings.DATABASE_URL_SYNC.endswith('/cmab_test')


@pytest.mark.parametrize('route', DOMAINS)
async def test_simultaneous_http_requests_create_once(admin_client, route):
    _, _, body, schema, table = DOMAINS[route]
    body = dict(body, material_code='C-'+uuid4().hex[:12]) if route=='materials' else body
    key = str(uuid4())
    replies = await asyncio.gather(*(admin_client.post('/api/v1/'+route,json=body,headers={'Idempotency-Key':key}) for _ in range(8)))
    assert all(r.status_code==201 for r in replies), [r.text for r in replies]
    assert all(r.json()==replies[0].json() for r in replies)
    assert all(r.headers['location']==replies[0].headers['location'] for r in replies)
    code = replies[0].json()['data'][table+'_code']
    engine = create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    try:
        async with engine.connect() as db:
            assert (await db.execute(text('SELECT count(*) FROM audit.audit_log WHERE entity_schema=:s AND entity_table=:t AND entity_code=:c AND action=\'CREATE\''),{'s':schema,'t':table,'c':code})).scalar_one()==1
    finally:
        await engine.dispose()


@pytest.mark.parametrize('route', DOMAINS)
async def test_second_connection_retries_until_first_transaction_commits(admin_client, monkeypatch, route):
    service, payload_class, body, _, table = DOMAINS[route]
    body = dict(body, material_code='C-'+uuid4().hex[:12]) if route=='materials' else body
    # 登录 fixture 已保证真实测试用户存在；本进程只模拟旧 Redis 未命中。
    class EmptyRedis:
        async def get(self, key): return None
    monkeypatch.setattr(idempotency,'get_redis',lambda: EmptyRedis())
    key, operation = str(uuid4()), route+':create'
    payload = payload_class(**body)
    canonical = payload.model_dump(mode='json')
    e1=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    e2=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    retried=asyncio.Event()
    attempts=0
    def observe(conn,cursor,statement,parameters,context,executemany):
        nonlocal attempts
        if 'pg_try_advisory_xact_lock' in statement:
            attempts+=1
            if attempts>=2:
                retried.set()
    event.listen(e2.sync_engine,'before_cursor_execute',observe)
    task=None
    try:
        async with async_sessionmaker(e1,expire_on_commit=False)() as first,async_sessionmaker(e2,expire_on_commit=False)() as second:
            actor=(await first.execute(select(User).where(User.username=='admin'))).scalar_one()
            actor_id=actor.user_id
            assert await IdempotencyService.check(first,actor_id,key,canonical,operation) is None
            detail=await service(first).create(payload,actor)
            response={'data':detail.model_dump(mode='json')}
            await IdempotencyService.save(first,actor_id,key,canonical,operation,201,response)
            task=asyncio.create_task(IdempotencyService.check(second,actor_id,key,canonical,operation))
            await asyncio.wait_for(retried.wait(),5)
            assert not task.done()
            await first.commit()
            hit=await task
            assert hit.body==response and hit.status_code==201
            await second.commit()
            # 已保存但回复未发送；通过另一条 HTTP 连接重试仍取到原记录。
            replay=await admin_client.post('/api/v1/'+route,json=body,headers={'Idempotency-Key':key})
            assert replay.status_code==201 and replay.json()['data'][table+'_code']==detail.model_dump()[table+'_code']
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        await e1.dispose()
        await e2.dispose()


@pytest.mark.parametrize('route', DOMAINS)
async def test_business_and_success_result_rollback_together(admin_client,monkeypatch,route):
    service,payload_class,body,schema,table=DOMAINS[route]
    body = dict(body, material_code='C-'+uuid4().hex[:12]) if route=='materials' else body
    class EmptyRedis:
        async def get(self,key):return None
    monkeypatch.setattr(idempotency,'get_redis',lambda:EmptyRedis())
    engine=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    key=str(uuid4())
    payload=payload_class(**body)
    try:
        async with async_sessionmaker(engine,expire_on_commit=False)() as db:
            actor=(await db.execute(select(User).where(User.username=='admin'))).scalar_one()
            actor_id=actor.user_id
            canonical=payload.model_dump(mode='json')
            assert await IdempotencyService.check(db,actor_id,key,canonical,route+':create') is None
            detail=await service(db).create(payload,actor)
            await IdempotencyService.save(db,actor_id,key,canonical,route+':create',201,{'data':detail.model_dump(mode='json')})
            await db.rollback()  # 模拟最终提交未成功，包括记录结果已写入的情况。
            code=detail.model_dump()[table+'_code']
            assert (await db.execute(text(f'SELECT count(*) FROM {schema}.{table} WHERE {table}_code=:c'),{'c':code})).scalar_one()==0
            assert await db.get(IdempotencyResult,(actor_id,UUID(key))) is None
            assert (await db.execute(text('SELECT count(*) FROM audit.audit_log WHERE entity_schema=:s AND entity_table=:t AND entity_code=:c'),{'s':schema,'t':table,'c':code})).scalar_one()==0
    finally:
        await engine.dispose()


async def test_fixed_window_changed_body_operation_and_cache_failure(admin_client,monkeypatch):
    key=str(uuid4())
    body={'category':'通用实验室设备','equipment_name':'固定窗口'}
    first=await admin_client.post('/api/v1/equipments',json=body,headers={'Idempotency-Key':key})
    assert first.status_code==201,first.text
    engine=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    try:
        async with async_sessionmaker(engine,expire_on_commit=False)() as db:
            actor=(await db.execute(select(User).where(User.username=='admin'))).scalar_one()
            actor_id=actor.user_id
            row=await db.get(IdempotencyResult,(actor_id,UUID(key)))
            expiry=row.expires_at
            class BrokenRedis:
                async def get(self,key):raise OSError('模拟缓存不可用')
            monkeypatch.setattr(idempotency,'get_redis',lambda:BrokenRedis())
            canonical=EquipmentCreate(**body).model_dump(mode='json')
            hit=await IdempotencyService.check(db,actor_id,key,canonical,'equipments:create')
            assert hit.body==first.json()
            assert row.expires_at==expiry
            await db.commit()
            for changed,operation in [(dict(canonical,notes='改了内容'),'equipments:create'),(canonical,'targets:create')]:
                with pytest.raises(DuplicateRequestError):
                    await IdempotencyService.check(db,actor_id,key,changed,operation)
                await db.rollback()
            with pytest.raises(IdempotencyUnavailableError):
                await IdempotencyService.check(db,actor_id,str(uuid4()),canonical,'equipments:create')
            await db.rollback()
        async with engine.begin() as db:
            await db.execute(text("UPDATE meta.idempotency_result SET expires_at=now()-interval '1 second' WHERE request_key=:key"),{'key':UUID(key)})
        new=await admin_client.post('/api/v1/equipments',json=body,headers={'Idempotency-Key':key})
        assert new.status_code==201 and new.json()['data']['equipment_code']!=first.json()['data']['equipment_code']
    finally:
        await engine.dispose()


async def test_legacy_redis_result_promoted_without_second_creation(admin_client):
    body={'category':'通用实验室设备','equipment_name':'旧缓存结果兼容'}
    original=await admin_client.post('/api/v1/equipments',json=body)
    assert original.status_code==201
    key=str(uuid4())
    engine=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    redis=redis_async.from_url(os.environ['REDIS_URL'],decode_responses=True)
    rkey=None
    try:
        async with engine.connect() as db:
            actor=(await db.execute(text('SELECT user_id FROM auth."user" WHERE username=\'admin\''))).scalar_one()
        rkey=f'idem:{actor}:{key}'
        await redis.setex(rkey,3600,json.dumps({'body_hash':_canonical_body_hash(EquipmentCreate(**body).model_dump(mode='json')),'status_code':201,'response_body':original.json(),'headers':{'Location':original.headers['location']}}))
        replay=await admin_client.post('/api/v1/equipments',json=body,headers={'Idempotency-Key':key})
        assert replay.status_code==201 and replay.json()==original.json()
        async with engine.connect() as db:
            ttl=(await db.execute(text('SELECT extract(epoch FROM expires_at-now()) FROM meta.idempotency_result WHERE request_key=:key'),{'key':UUID(key)})).scalar_one()
            assert 0<ttl<=3600
    finally:
        if rkey:
            await redis.delete(rkey)
        await redis.aclose()
        await engine.dispose()


@pytest.mark.parametrize('ttl', [-2, -1, 0])
async def test_legacy_result_seen_but_ttl_unknown_fails_before_creation(admin_client, monkeypatch, ttl):
    body = EquipmentCreate(equipment_name='兼容缓存异常', category='通用实验室设备').model_dump(mode='json')
    class UncertainRedis:
        async def get(self, key):
            return json.dumps({'body_hash': _canonical_body_hash(body), 'headers': {'Location': '/api/v1/equipments/EQP-OLD'},
                               'status_code': 201, 'response_body': {'data': {'equipment_code': 'EQP-OLD'}}})
        async def ttl(self, key):
            return ttl
    monkeypatch.setattr(idempotency, 'get_redis', lambda: UncertainRedis())
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
            key = str(uuid4())
            with pytest.raises(IdempotencyUnavailableError):
                await IdempotencyService.check(db, actor.user_id, key, body, 'equipments:create')
            await db.rollback()
            assert (await db.execute(select(IdempotencyResult).where(IdempotencyResult.request_key == UUID(key)))).scalar_one_or_none() is None
    finally:
        await engine.dispose()
