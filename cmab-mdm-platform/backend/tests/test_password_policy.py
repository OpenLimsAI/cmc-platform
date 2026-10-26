"""密码策略回归，所有写操作仅发生在 cmab_test。"""
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from app.core.exceptions import WeakPasswordError
from app.domains.auth.password_policy import PasswordPolicy, validate_strength
from sqlalchemy import create_engine, text

from tests.conftest import pg_connect_kwargs
from tests.test_admin_users import _payload


@pytest.fixture(autouse=True)
def require_isolated_database():
    assert os.environ.get("TEST_DB") == "cmab_test"


async def sql(query, *args):
    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        assert await conn.fetchval("SELECT current_database()") == "cmab_test"
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


async def user(admin_client, suffix, password="Aa1!bcde"):
    p = _payload(suffix)
    p["password"] = password
    r = await admin_client.post("/api/v1/users", json=p)
    assert r.status_code == 201, r.text
    return p


async def login(client, p, password=None):
    r = await client.post("/api/v1/auth/login", json={"username": p["username"], "password": password or p["password"]})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.parametrize("password", ["Aa1!bcde", "Aa1_bcde", "Ab1!中文ab"])
def test_valid_strength(password):
    validate_strength(password, PasswordPolicy())


@pytest.mark.parametrize("password", ["Aa1!bcd", "aa1!bcde", "AA1!BCDE", "Aa!!bcde", "Aa12bcde", "Aa1中文文字字", "Aa1!" + "x" * 69, "Aa1!" + "中" * 23])
def test_invalid_strength(password):
    with pytest.raises(WeakPasswordError):
        validate_strength(password, PasswordPolicy())


async def test_create_8_char_and_reject_weak_password(admin_client, unique_suffix):
    p = await user(admin_client, unique_suffix)
    assert (await sql('SELECT count(*) FROM auth.password_history h JOIN auth."user" u USING(user_id) WHERE u.username=$1', p["username"]))[0][0] == 1
    bad = _payload("weak" + unique_suffix)
    bad["password"] = "abcdefgh"
    r = await admin_client.post("/api/v1/users", json=bad)
    assert r.status_code == 400 and r.json()["code"] == 40010
    assert not await sql('SELECT user_id FROM auth."user" WHERE username=$1', bad["username"])


async def test_recent_five_includes_current_and_oldest_can_be_reused(admin_client, http_client, unique_suffix):
    p = await user(admin_client, unique_suffix, "Aa0!pwd0")
    current = p["password"]
    for i in range(1, 6):
        token = (await login(http_client, p, current))["access_token"]
        new = f"Aa{i}!pwd{i}"
        r = await http_client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                                   json={"old_password": current, "new_password": new})
        assert r.status_code == 200, r.text
        current = new
    data = await login(http_client, p, current)
    headers = {"Authorization": "Bearer " + data["access_token"]}
    for repeated in ("Aa1!pwd1", current):
        r = await http_client.post("/api/v1/auth/change-password", headers=headers,
                                   json={"old_password": current, "new_password": repeated})
        assert r.status_code == 400 and r.json()["code"] == 40011
    r = await http_client.post("/api/v1/auth/change-password", headers=headers,
                               json={"old_password": current, "new_password": "Aa0!pwd0"})
    assert r.status_code == 200, r.text
    # 不用 sleep：同一秒改密后，原通行证也必须失效。
    assert (await http_client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    r = await http_client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_expired_normal_password_only_allows_change_and_refresh(admin_client, http_client, unique_suffix):
    p = await user(admin_client, unique_suffix)
    await sql('UPDATE auth."user" SET password_expires_at=now()-interval \'1 day\' WHERE username=$1', p["username"])
    data = await login(http_client, p)
    assert data["user"]["must_change_password"]
    headers = {"Authorization": "Bearer " + data["access_token"]}
    assert (await http_client.get("/api/v1/auth/me", headers=headers)).json()["data"]["force_password_change"]
    assert (await http_client.get("/api/v1/auth/session-policy", headers=headers)).status_code == 200
    r = await http_client.get("/api/v1/substances", headers=headers)
    assert r.status_code == 403 and r.json()["meta"]["error"]["type"] == "password_change_required"
    refreshed = await http_client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    from app.core.security import decode_token
    assert decode_token(refreshed.json()["data"]["access_token"])["must_change_password"]
    r = await http_client.post("/api/v1/auth/change-password", headers=headers,
                               json={"old_password": p["password"], "new_password": "Bb2!cdef"})
    assert r.status_code == 200, r.text
    updated = await login(http_client, p, "Bb2!cdef")
    assert not updated["user"]["must_change_password"]
    r = await http_client.get("/api/v1/substances", headers={"Authorization": "Bearer " + updated["access_token"]})
    assert r.status_code == 200


async def test_new_tokens_end_at_password_deadline_and_existing_token_is_gated(admin_client, http_client, unique_suffix):
    p = await user(admin_client, unique_suffix)
    data = await login(http_client, p)
    headers = {"Authorization": "Bearer " + data["access_token"]}
    deadline = datetime.now(UTC) + timedelta(minutes=2)
    await sql('UPDATE auth."user" SET password_expires_at=$1 WHERE username=$2', deadline, p["username"])
    limited = await login(http_client, p)
    from app.core.security import decode_token
    assert decode_token(limited["access_token"])["exp"] <= int(deadline.timestamp())
    refreshed = await http_client.post("/api/v1/auth/refresh")
    assert decode_token(refreshed.json()["data"]["access_token"])["exp"] <= int(deadline.timestamp())
    await sql('UPDATE auth."user" SET password_expires_at=now()-interval \'1 second\' WHERE username=$1', p["username"])
    assert (await http_client.get("/api/v1/substances", headers=headers)).status_code == 403


async def test_expired_temporary_password_needs_admin_reset(admin_client, http_client, unique_suffix):
    p = await user(admin_client, unique_suffix)
    reset = await admin_client.post(f'/api/v1/users/{p["username"]}:reset-password')
    temp = reset.json()["data"]["temp_password"]
    data = await login(http_client, p, temp)
    await sql('UPDATE auth."user" SET password_expires_at=now()-interval \'1 second\' WHERE username=$1', p["username"])
    r = await http_client.post("/api/v1/auth/login", json={"username": p["username"], "password": temp})
    assert r.status_code == 403 and r.json()["meta"]["error"]["type"] == "temporary_password_expired"
    r = await http_client.post("/api/v1/auth/refresh")
    assert r.status_code == 403
    r = await http_client.post("/api/v1/auth/change-password", headers={"Authorization": "Bearer " + data["access_token"]},
                               json={"old_password": temp, "new_password": "Bb2!cdef"})
    assert r.status_code == 403
    reset = await admin_client.post(f'/api/v1/users/{p["username"]}:reset-password')
    await login(http_client, p, reset.json()["data"]["temp_password"])


async def test_rejected_change_does_not_write_history_or_audit(admin_client, http_client, unique_suffix):
    p = await user(admin_client, unique_suffix)
    data = await login(http_client, p)
    before = await sql('SELECT password_hash,password_expires_at FROM auth."user" WHERE username=$1', p["username"])
    history = await sql('SELECT count(*) FROM auth.password_history h JOIN auth."user" u USING(user_id) WHERE u.username=$1', p["username"])
    logs = await sql('SELECT count(*) FROM audit.audit_log WHERE entity_schema=\'auth\' AND entity_code=$1', p["username"])
    for old, new in [("wrong", "Bb2!cdef"), (p["password"], "abcdefgh"), (p["password"], p["password"])]:
        r = await http_client.post("/api/v1/auth/change-password", headers={"Authorization": "Bearer " + data["access_token"]},
                                   json={"old_password": old, "new_password": new})
        assert r.status_code in (400, 401)
    assert before == await sql('SELECT password_hash,password_expires_at FROM auth."user" WHERE username=$1', p["username"])
    assert history == await sql('SELECT count(*) FROM auth.password_history h JOIN auth."user" u USING(user_id) WHERE u.username=$1', p["username"])
    assert logs == await sql('SELECT count(*) FROM audit.audit_log WHERE entity_schema=\'auth\' AND entity_code=$1', p["username"])


def test_migration_baseline_dates_and_audit_exclude_passwords():
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.core.config import settings
    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")
    path = Path("alembic/versions/2026_10_13_1200_0064_auth_password_policy.py")
    spec = importlib.util.spec_from_file_location("password_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine(settings.DATABASE_URL_SYNC)
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text("DROP TABLE auth.password_history"))
                conn.execute(text("UPDATE meta.system_config SET config_value='12' WHERE config_key='password.min_length'"))
                conn.execute(text('UPDATE auth."user" SET password_expires_at=NULL WHERE username=\'readonly\''))
                conn.execute(text('UPDATE auth."user" SET password_expires_at=now()-interval \'1 day\' WHERE username=\'researcher\''))
                baseline = conn.execute(text('SELECT user_id,password_hash,password_expires_at FROM auth."user"')).all()
                before_log = conn.execute(text("SELECT max(log_id) FROM audit.audit_log")).scalar_one()
                module.op = Operations(MigrationContext.configure(conn))
                module.upgrade()
                assert conn.execute(text("SELECT config_value FROM meta.system_config WHERE config_key='password.min_length'")).scalar_one() == "8"
                assert conn.execute(text('SELECT count(*) FROM auth.password_history h JOIN auth."user" u USING(user_id) WHERE h.password_hash=u.password_hash')).scalar_one() == len(baseline)
                assert conn.execute(text('SELECT password_expires_at>now()+interval \'89 days\' FROM auth."user" WHERE username=\'readonly\'')).scalar_one()
                assert conn.execute(text('SELECT password_expires_at<now() FROM auth."user" WHERE username=\'researcher\'')).scalar_one()
                serialized = str(conn.execute(text("SELECT to_jsonb(l)::text FROM audit.audit_log l WHERE log_id>:id"), {"id": before_log}).all())
                assert all(row.password_hash not in serialized for row in baseline)
                with pytest.raises(RuntimeError, match="拒绝自动降级"):
                    module.downgrade()
            finally:
                tx.rollback()
    finally:
        engine.dispose()


@pytest.fixture
async def isolated_import_database(monkeypatch):
    from app.core.config import settings
    from app.scripts import import_users
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    monkeypatch.setattr(import_users, "engine", engine)
    monkeypatch.setattr(import_users, "AsyncSessionLocal", async_sessionmaker(engine, expire_on_commit=False))
    try:
        yield
    finally:
        await engine.dispose()


@pytest.mark.parametrize("weak", [False, True])
async def test_import_records_history_or_rejects_weak_password(tmp_path, monkeypatch, capsys, unique_suffix, weak, isolated_import_database):
    from app.scripts import import_users

    username = "import_" + unique_suffix
    path = tmp_path / "users.csv"
    path.write_text(f"姓名,工号,邮箱,角色,部门\n隔离导入,{username},{username}@test.local,READ_ONLY_USER,测试部\n")
    monkeypatch.setattr("sys.argv", ["import_users", "--file", str(path), "--dry-run"])
    assert await import_users.main() == 0
    assert not await sql('SELECT user_id FROM auth."user" WHERE username=$1', username)
    monkeypatch.setattr("sys.argv", ["import_users", "--file", str(path)])
    password = "abcdefgh" if weak else "Aa1!bcde"
    monkeypatch.setattr(import_users, "_generate_temp_password", lambda length: password)
    if weak:
        with pytest.raises(WeakPasswordError):
            await import_users.main()
        assert not await sql('SELECT user_id FROM auth."user" WHERE username=$1', username)
    else:
        assert await import_users.main() == 0
        record = (await sql('SELECT u.force_password_change,u.password_expires_at,u.password_hash, '
                            '(SELECT count(*) FROM auth.password_history h WHERE h.user_id=u.user_id '
                            'AND h.password_hash=u.password_hash) AS histories '
                            'FROM auth."user" u WHERE username=$1', username))[0]
        assert record["force_password_change"] and record["histories"] == 1
        assert datetime.now(UTC) + timedelta(days=6) < record["password_expires_at"] < datetime.now(UTC) + timedelta(days=8)
    logs = await sql('SELECT to_jsonb(l)::text AS body FROM audit.audit_log l WHERE entity_code=$1', username)
    assert len(logs) == (0 if weak else 1)
    assert all(password not in row["body"] for row in logs)
    if not weak:
        assert all(record["password_hash"] not in row["body"] for row in logs)
    capsys.readouterr()  # 发放输出只在此隔离测试中捕获，不进入验收报告。
