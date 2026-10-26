"""Mapping transactions on fresh PostgreSQL; contract stub is NOT browser E2E."""
import asyncio
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domains.auth.models import User
from app.domains.prs.pm_links import ProjectPMLinkService
from app.domains.prs.pm_reference import PMReference
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get('TEST_DB') == 'cmab_test'
    assert settings.DATABASE_URL_SYNC.endswith('/cmab_test')


class ContractReference:
    async def get(self, project_id):
        return PMReference(id=project_id, code='PM-TEST', name='合成执行项目', status='活跃', bindable=True)


async def new_project(client):
    result = await client.post('/api/v1/projects', json={'project_name': '关联隔离测试', 'project_type': 'cmc'})
    assert result.status_code == 201, result.text
    return result.json()['data']['project_code']


async def test_permissions_and_missing_verifier(admin_client, readonly_client, http_client):
    code = await new_project(admin_client)
    url = f'/api/v1/projects/{code}/pm-link'
    payload = {'pm_project_id': 'pm-no-verifier', 'change_reason': '验证默认拒绝写入'}
    assert (await http_client.get(url)).status_code == 401
    assert (await http_client.post(url, json=payload)).status_code == 401
    assert (await readonly_client.post(url, json=payload)).status_code == 403
    assert (await admin_client.post(url, json=payload)).status_code == 503
    assert (await admin_client.get(url)).json()['data']['link'] is None
    assert (await admin_client.get('/api/v1/projects/nonexistent/pm-link')).status_code == 404
    assert (await admin_client.get('/api/v1/integration/pm-projects/nonexistent')).status_code == 404


async def test_one_to_one_retry_concurrency_and_audit(admin_client):
    a, b = await new_project(admin_client), await new_project(admin_client)
    pm = 'pm-' + uuid4().hex
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async def bind(code, target):
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
            return await ProjectPMLinkService(db, ContractReference()).bind(code, target, '隔离测试人工确认关联', user)
    try:
        first, retry = await asyncio.gather(bind(a, pm), bind(a, pm))
        assert first['link']['link_id'] == retry['link']['link_id']
        with pytest.raises(ConflictError):
            await bind(b, pm)
        with pytest.raises(ConflictError):
            await bind(a, pm + '-other')
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM prs.project_pm_link WHERE pm_project_id=:id"), {'id': pm})).scalar_one() == 1
            assert (await conn.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table='project_pm_link' AND entity_id=:id"), {'id': first['link']['link_id']})).scalar_one() == 1
        result = await admin_client.get(f'/api/v1/integration/pm-projects/{pm}')
        assert result.json()['data']['project_code'] == a
        persisted = await admin_client.get(f'/api/v1/projects/{a}/pm-link')
        assert persisted.json()['data']['link']['pm_project_id'] == pm
        assert persisted.json()['data']['remote_status'] == 'not_configured'
        audit = await admin_client.get(f'/api/v1/projects/{a}/audit-logs')
        mapping_events = [row for row in audit.json()['data'] if row['entity_table'] == 'project_pm_link']
        assert len(mapping_events) == 1
        # The database itself rejects both duplicate sides, even without service prechecks.
        async with engine.connect() as conn:
            other_id = (await conn.execute(text('SELECT project_id FROM prs.project WHERE project_code=:code'), {'code': b})).scalar_one()
            for project_id, pm_id, constraint in [(first['link']['project_id'], pm + '-duplicate', 'uq_project_pm_link_project_id'),
                                                  (other_id, pm, 'uq_project_pm_link_pm_project_id')]:
                with pytest.raises(IntegrityError, match=constraint):
                    async with conn.begin_nested():
                        await conn.execute(text('''INSERT INTO prs.project_pm_link
                            (project_id,pm_project_id,pm_project_code,pm_project_name,verified_at,created_by,change_reason)
                            SELECT :project_id,:pm_id,pm_project_code,pm_project_name,verified_at,created_by,change_reason
                            FROM prs.project_pm_link WHERE link_id=:link_id'''),
                            {'project_id': project_id, 'pm_id': pm_id, 'link_id': first['link']['link_id']})
        # Exercise the real migration's nonempty downgrade guard without changing version/data.
        spec = importlib.util.spec_from_file_location('phase1_migration', Path(__file__).parents[1] / 'alembic/versions/2026_10_26_1800_0066_pm_project_link.py')
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        def refuse_downgrade(sync_conn):
            migration.op = Operations(MigrationContext.configure(sync_conn))
            with pytest.raises(RuntimeError, match='Refusing to drop nonempty'):
                migration.downgrade()
        async with engine.begin() as conn:
            await conn.run_sync(refuse_downgrade)
            assert (await conn.execute(text('SELECT count(*) FROM prs.project_pm_link WHERE pm_project_id=:id'), {'id': pm})).scalar_one() == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize('failure', ['missing', 'inactive'])
async def test_invalid_remote_never_persists_mapping(admin_client, failure):
    code = await new_project(admin_client)
    target = 'pm-' + uuid4().hex

    class InvalidReference:
        async def get(self, project_id):
            if failure == 'missing':
                raise NotFoundError('未找到 PM 项目')
            return PMReference(id=project_id, code='PM-OLD', name='已归档项目', status='已归档', bindable=False)

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
            with pytest.raises(NotFoundError if failure == 'missing' else BadRequestError):
                await ProjectPMLinkService(db, InvalidReference()).bind(code, target, '无效目标不得建立关联', user)
        assert (await admin_client.get(f'/api/v1/projects/{code}/pm-link')).json()['data']['link'] is None
    finally:
        await engine.dispose()
