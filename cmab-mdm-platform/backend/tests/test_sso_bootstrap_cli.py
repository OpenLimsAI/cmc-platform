"""Real disposable PostgreSQL CLI integration, never a shared database target."""
import asyncio
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from app.core.security import verify_password


@pytest.fixture
async def bootstrap_target(tmp_path):
    assert os.getenv("TEST_DB") == "cmab_test" and os.getenv("TEST_DB_HOST") == "postgres"
    assert urlsplit(os.environ["DATABASE_URL"]).path == "/cmab_test"
    name = "cmab_bootstrap_" + uuid.uuid4().hex[:16]
    assert re.fullmatch(r"cmab_bootstrap_[0-9a-f]{16}", name)
    args = {"host": "postgres", "port": 5432, "user": os.getenv("POSTGRES_DBA_USER", "postgres"),
            "password": os.environ["POSTGRES_DBA_PASSWORD"], "database": "postgres"}
    conn = await asyncpg.connect(**args)
    await conn.execute(f'CREATE DATABASE "{name}" OWNER "cmab_app"')
    await conn.close()
    env = dict(os.environ, TEST_DB=name, MDM_OIDC_ENABLED="true", MDM_NATIVE_LOGIN_ENABLED="false",
               MDM_OIDC_ISSUER_URL="https://identity.example.com", MDM_OIDC_ORGANIZATION="isolated",
               MDM_PUBLIC_URL="https://mdm.example.com/mdm", MDM_OIDC_ACCOUNT_STATUS_VISIBLE="true",
               MDM_OIDC_CLIENT_ID="bootstrap-unit-only", MDM_OIDC_CLIENT_SECRET=secrets.token_urlsafe(32),
               LOGURU_LEVEL="WARNING", APP_LOG_LEVEL="WARNING")
    for key in ["DATABASE_URL", "DATABASE_URL_SYNC"]:
        parsed = urlsplit(env[key])
        env[key] = urlunsplit(parsed._replace(path="/" + name))
    plan = {"database_host": "postgres", "database_port": 5432, "database": name,
            "issuer": env["MDM_OIDC_ISSUER_URL"], "organization": "isolated",
            "operator_subject": "explicit-one", "operator_ref": "ssh:isolated-fixture / approved bootstrap",
            "reason": "Approved fresh isolated fixture only",
            "accounts": [{"username": "isolated.one", "subject": "explicit-one", "email": "one@example.com", "full_name": "One"},
                         {"username": "isolated.two", "subject": "explicit-two", "email": "two@example.com", "full_name": "Two"}]}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    path.chmod(0o600)
    output = tmp_path / "credentials"
    output.mkdir(mode=0o700)
    try:
        for command in [[sys.executable, "-m", "app.scripts.bootstrap_test_db"], ["alembic", "upgrade", "head"]]:
            result = await asyncio.to_thread(subprocess.run, command, env=env, capture_output=True, timeout=60)
            assert result.returncode == 0, "Fresh test-only DB setup failed; private output suppressed"
        yield {"name": name, "env": env, "plan": path, "output": output, "args": dict(args, database=name)}
    finally:
        conn = await asyncpg.connect(**args)
        try:
            # The only target is the random DB created by this fixture above.
            assert re.fullmatch(r"cmab_bootstrap_[0-9a-f]{16}", name)
            await conn.execute(f'DROP DATABASE "{name}"')
        finally:
            await conn.close()


def command(target):
    return [sys.executable, "-m", "app.scripts.sso_bootstrap", "--plan", str(target["plan"]),
            "--secret-output-dir", str(target["output"]), "--apply"]


async def invoke(target):
    return await asyncio.to_thread(subprocess.run, command(target), env=target["env"],
                                   capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("account_count", [1, 2])
async def test_real_cli_bootstraps_and_retries_without_reissuing_credentials(bootstrap_target, account_count):
    target = bootstrap_target
    plan = json.loads(target["plan"].read_text())
    plan["accounts"] = plan["accounts"][:account_count]
    target["plan"].write_text(json.dumps(plan))
    first = await invoke(target)
    assert first.returncode == 0, "CLI failed; command output suppressed"
    reply = json.loads(first.stdout)
    assert reply["status"] == "created" and len(reply["accounts"]) == account_count
    conn = await asyncpg.connect(**target["args"])
    try:
        users = await conn.fetch('SELECT user_id,username,password_hash,force_password_change,password_expires_at > now() AS unexpired FROM auth."user" ORDER BY user_id')
        assert len(users) == account_count and all(u["force_password_change"] and u["unexpired"] for u in users)
        assert await conn.fetchval("SELECT count(*) FROM auth.oidc_identity") == account_count
        assert await conn.fetchval("SELECT count(*) FROM auth.user_role ur JOIN auth.role r USING(role_id) WHERE r.role_code='SYS_ADMIN'") == account_count
        assert await conn.fetchval("SELECT count(*) FROM auth.password_history") == account_count
        assert await conn.fetchval("SELECT count(*) FROM auth.login_history") == 0
        assert await conn.fetchval("SELECT count(*) FROM audit.e_signature") == 0
        assert await conn.fetchval("SELECT count(*) FROM audit.audit_log WHERE extra->>'actor_kind'='deployment_cli' AND user_id IS NULL") >= 1
        before = {}
        for user in users:
            path = target["output"] / (user["username"] + ".initial-password")
            assert path.stat().st_mode & 0o777 == 0o600
            password = path.read_text().strip()
            assert verify_password(password, user["password_hash"])
            assert password not in first.stdout and password not in first.stderr
            before[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        second = await invoke(target)
        assert second.returncode == 0 and json.loads(second.stdout)["status"] == "idempotent"
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target["output"].iterdir()} == before
        assert await conn.fetchval('SELECT count(*) FROM auth."user"') == account_count
    finally:
        await conn.close()


@pytest.mark.parametrize("failure", ["existing-file", "second-existing-file", "public-directory"])
async def test_secret_output_failure_leaves_no_users_or_mapping(bootstrap_target, failure):
    target = bootstrap_target
    old = target["output"] / ("isolated.two.initial-password" if failure == "second-existing-file" else "isolated.one.initial-password")
    if failure in {"existing-file", "second-existing-file"}:
        old.write_text("pre-existing-file-must-survive")
        old.chmod(0o600)
    else:
        target["output"].chmod(0o755)
    result = await invoke(target)
    assert result.returncode != 0
    conn = await asyncpg.connect(**target["args"])
    try:
        assert await conn.fetchval('SELECT count(*) FROM auth."user"') == 0
        assert await conn.fetchval("SELECT count(*) FROM auth.oidc_identity") == 0
        if failure in {"existing-file", "second-existing-file"}:
            assert old.read_text() == "pre-existing-file-must-survive"
            assert list(target["output"].iterdir()) == [old]
    finally:
        await conn.close()


async def test_concurrent_real_cli_calls_create_only_one_pair(bootstrap_target):
    results = await asyncio.gather(invoke(bootstrap_target), invoke(bootstrap_target))
    assert all(r.returncode == 0 for r in results), "Concurrent bootstrap failed; private output suppressed"
    assert sorted(json.loads(r.stdout)["status"] for r in results) == ["created", "idempotent"]
