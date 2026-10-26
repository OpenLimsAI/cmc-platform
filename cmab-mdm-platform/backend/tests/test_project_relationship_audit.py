"""关系取消保留原记录；失败不造成功审计；两个项目共享同一份事件。"""
import asyncio
import os

import pytest
from app.core.config import settings
from app.domains.auth.models import User
from app.domains.prs.schemas import ProjectRelationshipCreate
from app.domains.prs.services import ProjectService
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get('TEST_DB') == 'cmab_test'
    assert settings.DATABASE_URL_SYNC.endswith('/cmab_test')


async def projects(client):
    codes=[]
    for name in ['起点项目','终点项目']:
        r=await client.post('/api/v1/projects',json={'project_name':name,'project_type':'cmc'})
        assert r.status_code==201,r.text
        codes.append(r.json()['data']['project_code'])
    return codes


def relation(b):
    return {'to_project_code':b,'relationship_type':'derived_from','change_reason':'建立项目衍生关系'}


async def audit(client,code):
    r=await client.get(f'/api/v1/projects/{code}/audit-logs',params={'page_size':100})
    assert r.status_code==200,r.text
    return [x for x in r.json()['data'] if x['entity_table']=='project_relationship']


async def test_create_cancel_recreate_and_both_project_audits(admin_client):
    a,b=await projects(admin_client)
    url=f'/api/v1/projects/{a}/relationships'
    r=await admin_client.post(url,json=relation(b))
    assert r.status_code==201,r.text
    rid=r.json()['data']['relationship_id']
    aa,bb=await audit(admin_client,a),await audit(admin_client,b)
    assert [x['log_id'] for x in aa]==[x['log_id'] for x in bb] and len(aa)==1
    created=aa[0]
    assert created['action']=='CREATE' and created['username']=='admin' and created['reason']=='建立项目衍生关系'
    fields={v['field_name']:v['new_value'] for v in created['changes']}
    assert fields['from_project_code']==a and fields['to_project_code']==b
    assert fields['relationship_type']=='derived_from'
    for reason in ['取消已有衍生关系','重复取消关系']:
        cancelled=await admin_client.delete(url+f'/{rid}',json={'change_reason':reason})
        assert cancelled.status_code==204,cancelled.text
    assert (await admin_client.get(url)).json()['data']==[]
    cancelled_logs = await audit(admin_client, a)
    assert len(cancelled_logs) == 2
    assert cancelled_logs[0]['change_summary'] == f'{a} → {b} (derived_from)' 
    again=await admin_client.post(url,json=relation(b))
    assert again.status_code==201 and again.json()['data']['relationship_id']!=rid
    assert len(await audit(admin_client,a))==3
    assert [x['log_id'] for x in await audit(admin_client,a)]==[x['log_id'] for x in await audit(admin_client,b)]
    engine=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    try:
        async with engine.connect() as db:
            old=(await db.execute(text('SELECT deleted_at,deleted_by FROM prs.project_relationship WHERE relationship_id=:id'),{'id':rid})).one()
            assert old.deleted_at is not None and old.deleted_by is not None
            assert (await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table='project_relationship' AND entity_id=:id"),{'id':rid})).scalar_one()==2
    finally:
        await engine.dispose()


async def test_concurrent_create_and_cancel_leave_single_event(admin_client):
    a,b=await projects(admin_client)
    url=f'/api/v1/projects/{a}/relationships'
    replies=await asyncio.gather(*(admin_client.post(url,json=relation(b)) for _ in range(6)))
    assert sorted(r.status_code for r in replies)==[201,409,409,409,409,409]
    rid=next(r for r in replies if r.status_code==201).json()['data']['relationship_id']
    replies=await asyncio.gather(*(admin_client.delete(url+f'/{rid}',json={'change_reason':'同时取消项目关系'}) for _ in range(6)))
    assert all(r.status_code==204 for r in replies),[r.text for r in replies]
    assert sorted(r['action'] for r in await audit(admin_client,a))==['CREATE','DELETE']


@pytest.mark.parametrize('reason',[None,'短','    '])
async def test_invalid_reason_never_changes_relationship(admin_client,reason):
    a,b=await projects(admin_client)
    url=f'/api/v1/projects/{a}/relationships'
    body=relation(b)
    if reason is None:
        body.pop('change_reason')
    else:
        body['change_reason']=reason
    r=await admin_client.post(url,json=body)
    assert r.status_code==400,r.text
    assert (await admin_client.get(url)).json()['data']==[] and await audit(admin_client,a)==[]
    created=await admin_client.post(url,json=relation(b))
    assert created.status_code==201,created.text
    payload={} if reason is None else {'change_reason':reason}
    cancelled=await admin_client.delete(url+f"/{created.json()['data']['relationship_id']}",json=payload)
    assert cancelled.status_code==400
    assert len((await admin_client.get(url)).json()['data'])==1 and len(await audit(admin_client,a))==1


async def test_readonly_cannot_write_or_cancel(admin_client,readonly_client):
    a,b=await projects(admin_client)
    url=f'/api/v1/projects/{a}/relationships'
    assert (await readonly_client.post(url,json=relation(b))).status_code==403
    rid=(await admin_client.post(url,json=relation(b))).json()['data']['relationship_id']
    assert (await readonly_client.delete(url+f'/{rid}',json={'change_reason':'无权限尝试取消'})).status_code==403
    assert len(await audit(admin_client,a))==1


async def test_failed_commit_rolls_back_relationship_and_audit(admin_client,monkeypatch):
    a,b=await projects(admin_client)
    engine=create_async_engine(settings.DATABASE_URL,poolclass=NullPool)
    try:
        async with async_sessionmaker(engine,expire_on_commit=False)() as db:
            actor=(await db.execute(select(User).where(User.username=='admin'))).scalar_one()
            async def failed():raise RuntimeError('模拟提交失败')
            monkeypatch.setattr(db,'commit',failed)
            with pytest.raises(RuntimeError):
                await ProjectService(db).add_relationship(a,ProjectRelationshipCreate(**relation(b)),actor)
            await db.rollback()
            assert await audit(admin_client,a)==[]
            assert (await admin_client.get(f'/api/v1/projects/{a}/relationships')).json()['data']==[]
    finally:
        await engine.dispose()
