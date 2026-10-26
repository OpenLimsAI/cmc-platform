"""真实 HTTP + 两连接确定性排队；只在 cmab_test 产生账号和会话。"""
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.exceptions import TokenInvalidError
from app.core.security import create_refresh_token, decode_token
from app.domains.auth.models import RefreshToken, User
from app.domains.auth.refresh_branch_repair import affected_sessions, close_affected_sessions
from app.domains.auth.refresh_sessions import repeated_refresh_result
from app.domains.auth.services import AuthService
from httpx import AsyncClient
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from tests.conftest import BASE_URL
from tests.test_admin_users import _payload
from tests.test_password_policy import sql

UA = 'CMAB-isolated-refresh-test'
IP = '127.0.0.1'


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get('TEST_DB') == 'cmab_test'
    assert settings.DATABASE_URL_SYNC.endswith('/cmab_test')


@pytest.fixture
async def login_context(admin_client, unique_suffix):
    payload = _payload('rr' + unique_suffix)
    payload['password'] = 'Aa1!bcde'
    created = await admin_client.post('/api/v1/users', json=payload)
    assert created.status_code == 201, created.text
    async with AsyncClient(base_url=BASE_URL, headers={'User-Agent': UA}, timeout=15) as client:
        login = await client.post('/api/v1/auth/login', json={
            'username': payload['username'], 'password': payload['password'],
        })
        assert login.status_code == 200, login.text
        token = login.cookies['cmab_refresh_token']
        context = {'client': client, 'payload': payload, 'token': token,
                   'jti': decode_token(token)['jti'], 'user_id': login.json()['data']['user']['user_id']}
        try:
            yield context
        finally:
            await client.post('/api/v1/auth/logout', headers={'Cookie': 'cmab_refresh_token=' + token})


@pytest.fixture
async def sessions():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def rows(uid):
    return await sql('SELECT to_jsonb(t) AS value FROM auth.refresh_token t WHERE user_id=$1 ORDER BY jti', uid)


async def request_refresh(context, token=None, ua=UA):
    return await context['client'].post('/api/v1/auth/refresh', headers={
        'Cookie': 'cmab_refresh_token=' + (token or context['token']), 'User-Agent': ua,
    })


async def rotate(context):
    result = await request_refresh(context)
    assert result.status_code == 200, result.text
    return result


async def independent_login(context):
    async with AsyncClient(base_url=BASE_URL, headers={'User-Agent': UA}) as client:
        p = context['payload']
        response = await client.post('/api/v1/auth/login', json={'username': p['username'], 'password': p['password']})
        assert response.status_code == 200
        return response.cookies['cmab_refresh_token']


async def test_ten_simultaneous_http_requests_share_one_result(login_context):
    c = login_context
    before = await rows(c['user_id'])
    audit_before = await sql('SELECT count(*) FROM audit.audit_log WHERE user_id=$1', c['user_id'])
    results = await asyncio.gather(*(request_refresh(c) for _ in range(10)))
    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
    assert len({r.cookies['cmab_refresh_token'] for r in results}) == 1
    assert len({r.json()['data']['access_token'] for r in results}) == 1
    after = await rows(c['user_id'])
    assert len(before) == 1 and len(after) == 2
    assert await sql('SELECT count(*) FROM audit.audit_log WHERE user_id=$1', c['user_id']) == audit_before
    assert (await sql('SELECT failed_login_count FROM auth."user" WHERE user_id=$1', c['user_id']))[0][0] == 0


async def test_second_preloaded_connection_waits_and_reuses_fresh_result(login_context):
    c = login_context
    engine1 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    engine2 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    queued = asyncio.Event()
    def observe(conn, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement.upper():
            queued.set()
    event.listen(engine2.sync_engine, 'before_cursor_execute', observe)
    task = None
    try:
        async with async_sessionmaker(engine1, expire_on_commit=False)() as first, async_sessionmaker(engine2, expire_on_commit=False)() as second:
            cached = (await second.execute(select(RefreshToken).where(RefreshToken.jti == c['jti']))).scalar_one()
            assert cached.revoked_at is None
            await first.execute(select(User).where(User.user_id == c['user_id']).with_for_update())
            task = asyncio.create_task(AuthService(second).refresh(c['token'], IP, UA))
            await asyncio.wait_for(queued.wait(), timeout=5)
            assert not task.done()
            first_result = await AuthService(first).refresh(c['token'], IP, UA)
            second_result = await asyncio.wait_for(task, timeout=5)
            assert first_result[1] == second_result[1]
            assert first_result[0].access_token == second_result[0].access_token
            assert len(await rows(c['user_id'])) == 2
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine1.dispose()
        await engine2.dispose()


@pytest.mark.parametrize(('offset', 'allowed'), [(-0.001, False), (0, True), (4.999, True), (5, True), (5.001, False)])
async def test_exact_fixed_repeat_window(login_context, sessions, offset, allowed):
    c = login_context
    first = await rotate(c)
    async with sessions() as db:
        old = (await db.execute(select(RefreshToken).where(RefreshToken.jti == c['jti']))).scalar_one()
        now = old.revoked_at + timedelta(seconds=offset)
        if allowed:
            chosen = await repeated_refresh_result(db, old, now=now, ip=IP, ua=UA)
            assert chosen.jti == decode_token(first.cookies['cmab_refresh_token'])['jti']
        else:
            with pytest.raises(TokenInvalidError):
                await repeated_refresh_result(db, old, now=now, ip=IP, ua=UA)


async def test_repeated_response_does_not_extend_dates_or_fixed_window(login_context):
    c = login_context
    first = await rotate(c)
    before = await rows(c['user_id'])
    repeated = await request_refresh(c)
    assert repeated.status_code == 200
    assert repeated.cookies['cmab_refresh_token'] == first.cookies['cmab_refresh_token']
    assert decode_token(repeated.json()['data']['access_token'])['exp'] == decode_token(first.json()['data']['access_token'])['exp']
    assert await rows(c['user_id']) == before
    await sql("UPDATE auth.refresh_token SET revoked_at=now()-interval '6 seconds' WHERE jti=$1", c['jti'])
    assert (await request_refresh(c)).status_code == 401
    assert len(await rows(c['user_id'])) == 2


async def test_late_old_response_uses_latest_valid_descendant(login_context):
    c = login_context
    first = await rotate(c)
    second = await request_refresh(c, first.cookies['cmab_refresh_token'])
    assert second.status_code == 200
    repeated = await request_refresh(c)
    assert repeated.status_code == 200
    assert repeated.cookies['cmab_refresh_token'] == second.cookies['cmab_refresh_token']
    assert len(await rows(c['user_id'])) == 3


@pytest.mark.parametrize('different', ['ip', 'agent'])
async def test_different_source_cannot_retrieve_result(login_context, sessions, different):
    c = login_context
    await rotate(c)
    before = await rows(c['user_id'])
    async with sessions() as db:
        with pytest.raises(TokenInvalidError):
            await AuthService(db).refresh(c['token'], '127.0.0.2' if different == 'ip' else IP,
                                          'different-agent' if different == 'agent' else UA)
        await db.rollback()
    assert await rows(c['user_id']) == before


@pytest.mark.parametrize('reason', ['logout', 'password_changed', 'admin'])
async def test_revoked_result_cannot_be_retrieved(login_context, reason):
    c = login_context
    first = await rotate(c)
    child = decode_token(first.cookies['cmab_refresh_token'])['jti']
    await sql('UPDATE auth.refresh_token SET revoked_at=now(),revoked_reason=$1 WHERE jti=$2', reason, child)
    before = await rows(c['user_id'])
    assert (await request_refresh(c)).status_code == 401
    assert await rows(c['user_id']) == before


@pytest.mark.parametrize('status', ['locked', 'disabled'])
async def test_changed_account_state_blocks_repeated_refresh(login_context, status):
    c = login_context
    await rotate(c)
    await sql('UPDATE auth."user" SET status=$1 WHERE user_id=$2', status, c['user_id'])
    before = await rows(c['user_id'])
    assert (await request_refresh(c)).status_code == 401
    assert await rows(c['user_id']) == before


async def test_subject_must_own_refresh_record(login_context):
    c = login_context
    expiry = (await sql('SELECT expires_at FROM auth.refresh_token WHERE jti=$1', c['jti']))[0][0]
    token = create_refresh_token(subject=1, jti=c['jti'], expires_at=expiry)
    before = await rows(c['user_id'])
    assert (await request_refresh(c, token)).status_code == 401
    assert await rows(c['user_id']) == before


async def test_logout_closes_all_branches_of_only_this_login(login_context):
    c = login_context
    other = await independent_login(c)
    other_jti = decode_token(other)['jti']
    other_before = await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=$1', other_jti)
    first = await rotate(c)
    child = decode_token(first.cookies['cmab_refresh_token'])['jti']
    branch = str(uuid4())
    await sql('INSERT INTO auth.refresh_token(jti,user_id,issued_at,expires_at,session_started_at,ip_address,user_agent) '
              'SELECT $1,user_id,issued_at,expires_at,session_started_at,ip_address,user_agent FROM auth.refresh_token WHERE jti=$2', branch, child)
    logout = await c['client'].post('/api/v1/auth/logout', headers={'Cookie': 'cmab_refresh_token=' + c['token']})
    assert logout.status_code == 204
    assert (await sql('SELECT count(*) FROM auth.refresh_token WHERE jti=ANY($1::text[]) AND revoked_reason=\'logout\'', [child, branch]))[0][0] == 2
    assert (await request_refresh(c, first.cookies['cmab_refresh_token'])).status_code == 401
    assert await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=$1', other_jti) == other_before
    audit = await sql("SELECT to_jsonb(t) FROM audit.audit_log t WHERE user_id=$1 AND action='LOGOUT'", c['user_id'])
    assert len(audit) == 1
    assert (await c['client'].post('/api/v1/auth/logout', headers={'Cookie': 'cmab_refresh_token=' + c['token']})).status_code == 204
    assert await sql("SELECT to_jsonb(t) FROM audit.audit_log t WHERE user_id=$1 AND action='LOGOUT'", c['user_id']) == audit


@pytest.mark.parametrize('winner', ['refresh', 'logout', 'change_password'])
async def test_queued_refresh_or_logout_cannot_survive_session_end(login_context, winner):
    c = login_context
    e1 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    e2 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    queued = asyncio.Event()
    def observe(conn, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement.upper():
            queued.set()
    event.listen(e2.sync_engine, 'before_cursor_execute', observe)
    task = None
    try:
        async with async_sessionmaker(e1, expire_on_commit=False)() as first, async_sessionmaker(e2, expire_on_commit=False)() as second:
            user = (await first.execute(select(User).where(User.user_id == c['user_id'])
                                       .options(selectinload(User.roles)).with_for_update())).scalar_one()
            operation = AuthService(second).logout(c['token'], IP, UA) if winner == 'refresh' else AuthService(second).refresh(c['token'], IP, UA)
            task = asyncio.create_task(operation)
            await asyncio.wait_for(queued.wait(), timeout=5)
            assert not task.done()
            if winner == 'refresh':
                await AuthService(first).refresh(c['token'], IP, UA)
                await asyncio.wait_for(task, timeout=5)
            else:
                if winner == 'logout':
                    await AuthService(first).logout(c['token'], IP, UA)
                else:
                    await AuthService(first).change_password(user, c['payload']['password'], 'Bb2!cdef')
                with pytest.raises(TokenInvalidError):
                    await asyncio.wait_for(task, timeout=5)
                await second.rollback()
            assert (await sql('SELECT count(*) FROM auth.refresh_token WHERE user_id=$1 AND revoked_at IS NULL AND expires_at>now()', c['user_id']))[0][0] == 0
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await e1.dispose()
        await e2.dispose()


@pytest.mark.parametrize('operation', ['refresh', 'logout'])
async def test_failed_commit_restores_records_and_audit(login_context, sessions, monkeypatch, operation):
    c = login_context
    before = await rows(c['user_id'])
    audit_before = await sql('SELECT to_jsonb(t) FROM audit.audit_log t WHERE user_id=$1 ORDER BY log_id', c['user_id'])
    async with sessions() as db:
        async def fail_commit():
            raise RuntimeError('commit_failed')
        monkeypatch.setattr(db, 'commit', fail_commit)
        with pytest.raises(RuntimeError, match='commit_failed'):
            if operation == 'refresh':
                await AuthService(db).refresh(c['token'], IP, UA)
            else:
                await AuthService(db).logout(c['token'], IP, UA)
        await db.rollback()
    assert await rows(c['user_id']) == before
    assert await sql('SELECT to_jsonb(t) FROM audit.audit_log t WHERE user_id=$1 ORDER BY log_id', c['user_id']) == audit_before


async def add_historical_branch(context):
    now = datetime.now(UTC)
    start = now - timedelta(minutes=10)
    issued = now - timedelta(minutes=1)
    child, branch = str(uuid4()), str(uuid4())
    await sql('UPDATE auth.refresh_token SET issued_at=$1,session_started_at=$1,revoked_at=$2,revoked_reason=\'rotated\',rotated_to_jti=$3 WHERE jti=$4', start, issued, child, context['jti'])
    for ident in [child, branch]:
        await sql('INSERT INTO auth.refresh_token(jti,user_id,issued_at,expires_at,session_started_at,ip_address,user_agent) VALUES($1,$2,$3,$4,$5,$6,$7)',
                  ident, context['user_id'], issued, now+timedelta(minutes=20), start, IP, UA)
    return child, branch


async def test_historical_repair_preview_apply_audit_and_other_login_preserved(login_context, sessions):
    c = login_context
    child, branch = await add_historical_branch(c)
    other = await independent_login(c)
    other_jti = decode_token(other)['jti']
    other_before = await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=$1', other_jti)
    before = await rows(c['user_id'])
    audit_before = await sql('SELECT to_jsonb(t) FROM audit.audit_log t ORDER BY log_id')
    async with sessions() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        preview = await affected_sessions(db)
        assert any(r['user_id'] == c['user_id'] and r['branches'] == 1 for r in preview)
        await db.rollback()
    assert await rows(c['user_id']) == before
    assert await sql('SELECT to_jsonb(t) FROM audit.audit_log t ORDER BY log_id') == audit_before
    async with sessions() as db:
        actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
        report = await close_affected_sessions(db, actor=actor, reason='隔离演练')
        await db.commit()
        assert report['revoked_records'] >= 2
    assert len(await rows(c['user_id'])) == len(before)
    assert (await sql('SELECT count(*) FROM auth.refresh_token WHERE jti=ANY($1::text[]) AND revoked_reason=\'admin\'', [child, branch]))[0][0] == 2
    assert await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=$1', other_jti) == other_before
    logs = await sql("SELECT to_jsonb(t) AS value FROM audit.audit_log t WHERE entity_id=$1 AND extra->>'operation'='close_refresh_branches'", c['user_id'])
    assert len(logs) == 1
    serialized = str(logs)
    assert all(secret not in serialized for secret in [child, branch, c['token'], c['payload']['password']])
    async with sessions() as db:
        actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
        assert (await close_affected_sessions(db, actor=actor, reason='重复隔离演练'))['closed_sessions'] == 0
        await db.commit()


async def test_repair_commit_failure_rolls_back_all_effects(login_context, sessions, monkeypatch):
    c = login_context
    await add_historical_branch(c)
    before = await rows(c['user_id'])
    audit_before = await sql('SELECT count(*) FROM audit.audit_log')
    async with sessions() as db:
        actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
        await close_affected_sessions(db, actor=actor, reason='失败演练')
        async def fail_commit():
            raise RuntimeError('repair_commit_failed')
        monkeypatch.setattr(db, 'commit', fail_commit)
        with pytest.raises(RuntimeError, match='repair_commit_failed'):
            await db.commit()
        await db.rollback()
    assert await rows(c['user_id']) == before
    assert await sql('SELECT count(*) FROM audit.audit_log') == audit_before


async def run_repair_cli(*args):
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'app.scripts.close_refresh_branches', *args,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(process.communicate(), timeout=15)
    return process.returncode, out.decode(), err.decode()


async def test_cli_default_preview_and_guards_do_not_write(login_context):
    c = login_context
    await add_historical_branch(c)
    before = await rows(c['user_id'])
    for args in [('--expected-database', 'cmab_test'),
                 ('--expected-database', 'wrong_database'),
                 ('--expected-database', 'cmab_test', '--apply'),
                 ('--expected-database', 'cmab_test', '--apply', '--actor', 'readonly', '--reason', '隔离演练')]:
        status, out, _ = await run_repair_cli(*args)
        if len(args) == 2 and args[1] == 'cmab_test':
            assert status == 0 and json.loads(out)['mode'] == 'preview'
        else:
            assert status != 0
        assert await rows(c['user_id']) == before


async def test_cli_explicit_apply_only_in_test_database(login_context):
    c = login_context
    child, branch = await add_historical_branch(c)
    status, out, err = await run_repair_cli('--expected-database', 'cmab_test', '--apply', '--actor', 'admin', '--reason', '隔离 CLI 演练')
    assert status == 0, err
    assert json.loads(out)['revoked_records'] >= 2
    assert (await sql('SELECT count(*) FROM auth.refresh_token WHERE jti=ANY($1::text[]) AND revoked_reason=\'admin\'', [child, branch]))[0][0] == 2


async def test_legacy_empty_session_start_survives_repeat_and_logout(login_context):
    c = login_context
    await sql('UPDATE auth.refresh_token SET session_started_at=NULL WHERE jti=$1', c['jti'])
    issued = (await sql('SELECT issued_at FROM auth.refresh_token WHERE jti=$1', c['jti']))[0][0]
    first = await rotate(c)
    child = decode_token(first.cookies['cmab_refresh_token'])['jti']
    assert (await sql('SELECT session_started_at FROM auth.refresh_token WHERE jti=$1', child))[0][0] == issued
    assert (await request_refresh(c)).status_code == 200
    assert (await c['client'].post('/api/v1/auth/logout', headers={'Cookie': 'cmab_refresh_token=' + c['token']})).status_code == 204
    assert (await sql('SELECT revoked_reason FROM auth.refresh_token WHERE jti=$1', child))[0][0] == 'logout'


async def test_policy_change_cannot_extend_a_repeated_result(login_context):
    c = login_context
    first = await rotate(c)
    saved = (await sql("SELECT config_value,updated_at FROM meta.system_config WHERE config_key='session.access_token_minutes'"))[0]
    before = await rows(c['user_id'])
    try:
        await sql("UPDATE meta.system_config SET config_value='16',updated_at=now() WHERE config_key='session.access_token_minutes'")
        assert (await request_refresh(c)).status_code == 401
        assert await rows(c['user_id']) == before
        normal = await request_refresh(c, first.cookies['cmab_refresh_token'])
        assert normal.status_code == 200
    finally:
        await sql("UPDATE meta.system_config SET config_value=$1,updated_at=$2 WHERE config_key='session.access_token_minutes'", saved['config_value'], saved['updated_at'])


async def test_expired_branch_ancestor_with_live_descendant_is_closed(login_context, sessions):
    c = login_context
    child, branch = await add_historical_branch(c)
    grandchild = str(uuid4())
    await sql('INSERT INTO auth.refresh_token(jti,user_id,issued_at,expires_at,session_started_at,ip_address,user_agent) '
              'SELECT $1,user_id,now(),expires_at,session_started_at,ip_address,user_agent FROM auth.refresh_token WHERE jti=$2', grandchild, branch)
    await sql("UPDATE auth.refresh_token SET revoked_at=now(),revoked_reason='rotated',rotated_to_jti=$1 WHERE jti=$2", grandchild, branch)
    await sql("UPDATE auth.refresh_token SET expires_at=now()-interval '1 second' WHERE jti=ANY($1::text[])", [child, branch])
    expired_before = await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=ANY($1::text[]) ORDER BY jti', [child, branch])
    async with sessions() as db:
        assert any(s['user_id'] == c['user_id'] for s in await affected_sessions(db))
        actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
        report = await close_affected_sessions(db, actor=actor, reason='后续分支隔离演练')
        await db.commit()
        assert report['closed_sessions'] == 1 and report['revoked_records'] == 1
    assert await sql('SELECT to_jsonb(t) FROM auth.refresh_token t WHERE jti=ANY($1::text[]) ORDER BY jti', [child, branch]) == expired_before
    assert (await sql('SELECT revoked_reason FROM auth.refresh_token WHERE jti=$1', grandchild))[0][0] == 'admin'


async def test_similar_time_but_different_source_is_not_repaired(login_context, sessions):
    c = login_context
    _, branch = await add_historical_branch(c)
    await sql("UPDATE auth.refresh_token SET user_agent='other-source' WHERE jti=$1", branch)
    before = await rows(c['user_id'])
    async with sessions() as db:
        assert not any(s['user_id'] == c['user_id'] for s in await affected_sessions(db))
        actor = (await db.execute(select(User).where(User.username == 'admin'))).scalar_one()
        assert (await close_affected_sessions(db, actor=actor, reason='不匹配来源隔离演练'))['closed_sessions'] == 0
        await db.commit()
    assert await rows(c['user_id']) == before
