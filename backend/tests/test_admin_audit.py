"""Phase 5.A / M5.3 全局审计 + 签名查询测试

覆盖：
- GET /audit-logs 基本列表 + 分页
- 按 username / action / entity_table / entity_code / date_from / q 过滤
- 字段级 changes 非空（UPDATE 场景）
- POST /audit-logs:export 返回 CSV（含 BOM + headers + Content-Disposition）
- 导出筛选生效
- GET /signatures 列表（schema 验证；不假设特定数据存在）
- readonly 403
"""
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import pg_connect_kwargs


# ============== helper ==============
async def _create_substance(admin_client, suffix: str) -> str:
    """快速创建一个物质并触发一次 UPDATE 让 audit_log 有 changes"""
    r = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"AUD-{suffix}",
            "preferred_name": f"audit test {suffix}",
            "confidentiality": "internal",
        },
    )
    assert r.status_code == 201, r.text
    code = r.json()["data"]["substance_code"]
    # UPDATE 一次让 change_history 有内容
    detail = await admin_client.get(f"/api/v1/substances/{code}")
    version = detail.json()["data"]["version"]
    r2 = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={
            "version": version,
            "preferred_name": f"audit test {suffix} updated",
            "change_reason": "M5.3 全局审计测试",
        },
    )
    assert r2.status_code == 200, r2.text
    return code


# ============== 基本列表 ==============
@pytest.mark.asyncio
async def test_list_audit_logs_basic(admin_client):
    r = await admin_client.get("/api/v1/audit-logs?page=1&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "pagination" in body["meta"]
    assert body["meta"]["pagination"]["page"] == 1
    assert body["meta"]["pagination"]["page_size"] == 5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account_case",
    ["active", "locked", "disabled", "soft_deleted", "empty_name", "no_user_id", "missing_user"],
)
async def test_audit_logs_current_name_preserves_history(admin_client, unique_suffix, account_case):
    """姓名按用户 ID 匹配；账号状态或缺失资料不能丢弃审计记录。"""
    import asyncpg

    kwargs = pg_connect_kwargs()
    assert kwargs["database"] == "cmab_test", "此用例只能在隔离 cmab_test 库执行"
    conn = await asyncpg.connect(**kwargs)
    try:
        assert await conn.fetchval("SELECT current_database()") == "cmab_test"
        username = f"audit_name_{unique_suffix}"
        full_name = "" if account_case == "empty_name" else "审计测试员工"
        status = account_case if account_case in {"locked", "disabled"} else "active"
        user_id = await conn.fetchval(
            'INSERT INTO auth."user" (username, email, password_hash, full_name, status, deleted_at) '
            "VALUES ($1, $2, 'unused-test-hash', $3, $4, $5) RETURNING user_id",
            username,
            f"{username}@test.com",
            full_name,
            status,
            datetime.now(UTC) if account_case == "soft_deleted" else None,
        )
        log_user_id = user_id
        if account_case == "no_user_id":
            log_user_id = None
        elif account_case == "missing_user":
            log_user_id = -1
        code = f"AUD-NAME-{unique_suffix}"
        for _ in range(2):
            await conn.execute(
                "INSERT INTO audit.audit_log (user_id, username, action, entity_code) "
                "VALUES ($1, $2, 'LOGIN', $3)",
                log_user_id, username, code,
            )

        response = await admin_client.get(
            f"/api/v1/audit-logs?entity_code={code}&username={username}&page_size=1"
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["meta"]["pagination"]["total"] == 2
        assert len(body["data"]) == 1
        item = body["data"][0]
        assert item["username"] == username
        assert item["user_id"] == log_user_id
        assert item["full_name"] == (
            None if account_case in {"empty_name", "no_user_id", "missing_user"} else full_name
        )

        if account_case == "active":
            # 账号更名时按 ID 取当前姓名，历史工号及操作保持原值。
            await conn.execute(
                'UPDATE auth."user" SET username=$1, full_name=$2 WHERE user_id=$3',
                f"renamed_{unique_suffix}", "更新后的姓名", user_id,
            )
            updated = await admin_client.get(f"/api/v1/audit-logs?entity_code={code}")
            assert updated.status_code == 200
            assert all(row["username"] == username for row in updated.json()["data"])
            assert all(row["full_name"] == "更新后的姓名" for row in updated.json()["data"])
            assert all(row["action"] == "LOGIN" for row in updated.json()["data"])
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_filter_by_action_create(admin_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    r = await admin_client.get(
        f"/api/v1/audit-logs?action=CREATE&entity_code={code}"
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert all(item["action"] == "CREATE" for item in data)
    assert all(item["entity_code"] == code for item in data)


@pytest.mark.asyncio
async def test_filter_by_entity_table_and_username(admin_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    r = await admin_client.get(
        f"/api/v1/audit-logs?entity_table=substance&username=admin&entity_code={code}"
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 2  # CREATE + UPDATE
    assert all(item["entity_table"] == "substance" for item in data)
    assert all(item["username"] == "admin" for item in data)


@pytest.mark.asyncio
async def test_filter_by_q(admin_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    # entity_code ILIKE 包含编码片段
    r = await admin_client.get(f"/api/v1/audit-logs?q={code}")
    assert r.status_code == 200
    assert all(item["entity_code"] == code for item in r.json()["data"])

    # reason ILIKE 命中 UPDATE 的 change_reason
    r2 = await admin_client.get("/api/v1/audit-logs?q=M5.3 全局审计测试")
    assert r2.status_code == 200
    matched = r2.json()["data"]
    assert any(item["entity_code"] == code for item in matched)


@pytest.mark.asyncio
async def test_filter_by_date_range(admin_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    # 正向：用半小时前作为 from（应命中刚创建的记录）
    now = datetime.now(UTC)
    date_from = (now - timedelta(minutes=30)).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    r_hit = await admin_client.get(
        f"/api/v1/audit-logs?date_from={date_from}&entity_code={code}"
    )
    assert r_hit.status_code == 200
    assert r_hit.json()["meta"]["pagination"]["total"] >= 1
    assert any(
        item["entity_code"] == code for item in r_hit.json()["data"]
    )

    # 反向：用未来时间作为 from 应该返回 0 行
    future = "2099-12-31T00:00:00Z"
    r = await admin_client.get(
        f"/api/v1/audit-logs?date_from={future}&entity_code={code}"
    )
    assert r.status_code == 200
    assert r.json()["meta"]["pagination"]["total"] == 0

    # 半小时前作为 to 应该不包含刚创建的（dev DB 时钟可能有点偏移，做容差）
    past = "2000-01-01T00:00:00Z"
    r2 = await admin_client.get(
        f"/api/v1/audit-logs?date_to={past}&entity_code={code}"
    )
    assert r2.status_code == 200
    assert r2.json()["meta"]["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_audit_logs_includes_changes(admin_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    # 查 UPDATE 行的 changes
    r = await admin_client.get(
        f"/api/v1/audit-logs?action=UPDATE&entity_code={code}"
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    # 至少其中一条有 changes（v3 触发器：UPDATE 写 change_history）
    assert any(len(item.get("changes") or []) > 0 for item in data)


# ============== CSV 导出 ==============
@pytest.mark.asyncio
async def test_export_csv_with_filter(admin_client, http_client, unique_suffix):
    code = await _create_substance(admin_client, unique_suffix)

    # 用 entity_code 精确过滤导出
    r = await http_client.post(
        f"/api/v1/audit-logs:export?entity_code={code}",
        headers={"Authorization": admin_client._headers["Authorization"]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "audit_logs_" in cd and ".csv" in cd

    body = r.text
    # UTF-8 BOM
    assert body.startswith("﻿") or body.startswith("ï»¿")
    # 表头
    assert "log_id,timestamp,username" in body
    # 至少 2 行（CREATE + UPDATE）
    # 注：CSV 第一行是 header，所以 splitlines() 后业务行 >= 2
    lines = [line for line in body.splitlines() if line.strip()]
    assert len(lines) >= 3  # header + CREATE + UPDATE
    # 所有数据行都含 entity_code
    for line in lines[1:]:
        assert code in line

    # X-Row-Count 头
    assert int(r.headers.get("x-row-count", 0)) >= 2


@pytest.mark.asyncio
async def test_export_csv_no_filter_large_volume(admin_client, http_client):
    """回归：无筛选导出时实际可能有 >32767 行 audit_log。

    实现必须用 SQL 子查询而不是 Python 列表 IN 绑定（asyncpg 单次绑定上限 32767）。
    此测试验证全量导出不报 500。
    """
    r = await http_client.post(
        "/api/v1/audit-logs:export",
        headers={"Authorization": admin_client._headers["Authorization"]},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    # 用真正的 CSV 解析器统计记录数：reason/changes 单元格可能含被引号包裹的换行，
    # 简单 splitlines() 会把单条记录算成多行，必须按 CSV record 计数。
    import csv
    import io

    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    rows = [row for row in rows if row]  # 去掉尾部空记录
    assert len(rows) >= 1  # 至少 header 行
    # 记录数 = X-Row-Count + 1 header（不超过 50000 上限）
    row_count = int(r.headers.get("x-row-count", "0"))
    assert row_count <= 50000
    assert len(rows) == row_count + 1


@pytest.mark.asyncio
async def test_export_csv_empty_with_strict_filter(admin_client, http_client):
    """筛选不存在的 entity_code 应该返回 CSV header-only + 0 行"""
    r = await http_client.post(
        "/api/v1/audit-logs:export?entity_code=NOPE_DOES_NOT_EXIST_X12Z",
        headers={"Authorization": admin_client._headers["Authorization"]},
    )
    assert r.status_code == 200
    lines = [line for line in r.text.splitlines() if line.strip()]
    assert len(lines) == 1  # 仅 header
    assert int(r.headers.get("x-row-count", 0)) == 0


# ============== 签名列表 ==============
@pytest.mark.asyncio
async def test_list_signatures_schema(admin_client):
    """不假设特定数据存在，只验响应壳层 + 字段类型"""
    r = await admin_client.get("/api/v1/signatures?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "pagination" in body["meta"]
    # 若有数据，验关键字段
    for item in body["data"]:
        assert "signature_id" in item
        assert "signature_meaning" in item
        assert "signed_at" in item
        assert "signature_hash" in item


@pytest.mark.asyncio
async def test_signature_filter_meaning(admin_client):
    """meaning='approve' 过滤应只返回 approve 类型"""
    r = await admin_client.get("/api/v1/signatures?signature_meaning=approve")
    assert r.status_code == 200
    for item in r.json()["data"]:
        assert item["signature_meaning"] == "approve"


# ============== 权限 ==============
@pytest.mark.asyncio
async def test_readonly_forbidden(readonly_client):
    r1 = await readonly_client.get("/api/v1/audit-logs")
    assert r1.status_code == 403

    r2 = await readonly_client.post("/api/v1/audit-logs:export")
    assert r2.status_code == 403

    r3 = await readonly_client.get("/api/v1/signatures")
    assert r3.status_code == 403
