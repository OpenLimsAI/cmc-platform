"""
M2.5.2 安全收尾测试

覆盖：
- 改密后旧 access_token 立即失效（password_changed_at + JWT.iat 比较）
- 连续 5 次错密码登录 → 账户锁定
- 锁定超过 LOGIN_LOCK_DURATION_MINUTES 后自动解锁（通过直接改 DB locked_at 模拟时间快进）
- 签名失败旁路审计：错密码触发 → audit_log SIGN 失败记录持久化，failed_login_count++
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest


# ============== helper ==============
async def _create_throwaway_user(admin_client, http_client, unique_suffix):
    """直接通过 DB 创建临时用户用于测试。绕过用户管理 API（M2.5.2 暂未上线）"""
    import asyncpg

    suffix = unique_suffix
    username = f"sec_{suffix}"
    password = "TestSec@2026!"
    conn = await asyncpg.connect(
        host="postgres", port=5432, user="cmab_app",
        password="__REDACTED_POSTGRES_PASSWORD__", database="cmab_mdm",
    )
    # bcrypt hash 生成（与 backend 相同 schema）
    import bcrypt
    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    await conn.execute(
        """
        INSERT INTO auth.user (
            username, email, password_hash, full_name, status, failed_login_count
        ) VALUES ($1, $2, $3, $4, 'active', 0)
        """,
        username, f"{username}@test.com", pwd_hash, f"Test {suffix}",
    )
    # 给 READ_ONLY 角色避免触发权限相关错误
    await conn.execute(
        """
        INSERT INTO auth.user_role (user_id, role_id)
        SELECT u.user_id, r.role_id
          FROM auth.user u, auth.role r
         WHERE u.username = $1 AND r.role_code = 'READ_ONLY_USER'
        """,
        username,
    )
    await conn.close()
    return username, password


async def _login(http_client, username, password):
    return await http_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


async def _db_exec(sql, *args):
    import asyncpg
    conn = await asyncpg.connect(
        host="postgres", port=5432, user="cmab_app",
        password="__REDACTED_POSTGRES_PASSWORD__", database="cmab_mdm",
    )
    try:
        return await conn.fetchrow(sql, *args)
    finally:
        await conn.close()


# ============== JWT 失效 ==============
@pytest.mark.asyncio
async def test_change_password_invalidates_old_tokens(http_client, admin_client, unique_suffix):
    """改密后，改密前签发的 access_token 立即作废"""
    username, password = await _create_throwaway_user(admin_client, http_client, unique_suffix)

    # 1) 登录拿 token
    r = await _login(http_client, username, password)
    assert r.status_code == 200
    old_token = r.json()["data"]["access_token"]

    # 2) 用旧 token 调 /me 应能成功
    me = await http_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert me.status_code == 200

    # 3) 改密码
    new_password = "TestSec@2027!"
    # 等 1 秒，确保 password_changed_at > token.iat（JWT iat 是秒级整数）
    await asyncio.sleep(1.1)
    cp = await http_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"old_password": password, "new_password": new_password},
    )
    assert cp.status_code in (200, 204), cp.text

    # 4) 用旧 token 调 /me 应 401
    me2 = await http_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert me2.status_code == 401
    assert me2.json()["meta"]["error"]["type"] == "token_invalid"

    # 5) 用新密码重新登录获取新 token，可访问
    r2 = await _login(http_client, username, new_password)
    assert r2.status_code == 200
    new_token = r2.json()["data"]["access_token"]
    me3 = await http_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert me3.status_code == 200


# ============== 登录锁定 + 自动解锁 ==============
@pytest.mark.asyncio
async def test_lockout_after_max_failed_attempts(http_client, admin_client, unique_suffix):
    """连续 5 次错密码 → 账户锁定 + locked_at 写入"""
    username, password = await _create_throwaway_user(admin_client, http_client, unique_suffix)

    for i in range(5):
        r = await _login(http_client, username, "WRONG_PASSWORD")
        # 第 5 次触发锁定 → 423；前 4 次 401
        if i < 4:
            assert r.status_code == 401, f"attempt {i}: {r.text}"
        else:
            assert r.status_code == 423, f"attempt {i}: {r.text}"

    # DB 中应已锁定且 locked_at 写入
    row = await _db_exec(
        "SELECT status, failed_login_count, locked_at FROM auth.user WHERE username=$1",
        username,
    )
    assert row["status"] == "locked"
    assert row["failed_login_count"] >= 5
    assert row["locked_at"] is not None

    # 此时即使输对密码也应 423
    r = await _login(http_client, username, password)
    assert r.status_code == 423


@pytest.mark.asyncio
async def test_auto_unlock_after_duration(http_client, admin_client, unique_suffix):
    """通过把 locked_at 改成早于 LOGIN_LOCK_DURATION_MINUTES 前，模拟时间经过"""
    username, password = await _create_throwaway_user(admin_client, http_client, unique_suffix)

    # 触发锁定
    for _ in range(5):
        await _login(http_client, username, "WRONG_PASSWORD")

    # 模拟 31 分钟前被锁
    await _db_exec(
        "UPDATE auth.user SET locked_at = NOW() - INTERVAL '31 minutes' WHERE username=$1",
        username,
    )

    # 输对密码应自动解锁并登录成功
    r = await _login(http_client, username, password)
    assert r.status_code == 200, r.text

    # DB 状态恢复
    row = await _db_exec(
        "SELECT status, failed_login_count, locked_at FROM auth.user WHERE username=$1",
        username,
    )
    assert row["status"] == "active"
    assert row["failed_login_count"] == 0
    assert row["locked_at"] is None


# ============== 签名失败旁路审计 ==============
@pytest.mark.asyncio
async def test_signature_failure_persists_audit_independently(admin_client, unique_suffix):
    """错密码签名 → 主事务 rollback，但 SIGN 失败 audit + failed_login_count 应留存"""
    # 用 admin 创建一个 substance，然后错密码 :approve
    create = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-SECAUD-{unique_suffix}",
            "preferred_name": f"sec audit {unique_suffix}",
        },
    )
    scode = create.json()["data"]["substance_code"]

    # 记录 admin 的 failed_login_count 基线
    before = await _db_exec(
        "SELECT failed_login_count FROM auth.user WHERE username='admin'"
    )
    base_count = before["failed_login_count"]

    # 错密码 :approve
    r = await admin_client.post(
        f"/api/v1/substances/{scode}:approve",
        json={
            "comment": "测试签名失败旁路审计",
            "signature": {"password": "wrong_pwd", "reason": "测试签名失败旁路审计签名理由"},
        },
    )
    assert r.status_code == 401
    assert r.json()["meta"]["error"]["type"] == "signature_invalid"

    # SIGN 失败 audit 应持久化
    audit = await _db_exec(
        """
        SELECT log_id, action, reason FROM audit.audit_log
         WHERE action='SIGN' AND entity_code=$1
         ORDER BY log_id DESC LIMIT 1
        """,
        scode,
    )
    assert audit is not None, "签名失败的 audit_log 应已持久化"
    assert "密码错误" in audit["reason"]

    # failed_login_count 应已 +1
    after = await _db_exec(
        "SELECT failed_login_count FROM auth.user WHERE username='admin'"
    )
    assert after["failed_login_count"] == base_count + 1

    # 重置 admin 状态（避免污染后续测试）
    await _db_exec(
        "UPDATE auth.user SET failed_login_count=0, status='active', locked_at=NULL WHERE username='admin'"
    )
