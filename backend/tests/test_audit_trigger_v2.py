"""M2.0 回归：fn_audit_trigger v2 行为

覆盖：
1. child 表（substance_xref）audit_log.entity_code 通过 parent 查回 substance_code
2. change_history 不再记录 updated_by 字段
3. list_substances 批量 xref 加载正确（N+1 修复后的功能回归）
"""
import pytest


@pytest.mark.asyncio
async def test_xref_audit_log_inherits_parent_entity_code(admin_client, unique_suffix):
    """加 xref 应在 audit_log 写入 entity_table=substance_xref 但 entity_code=父 substance_code"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AUD-{unique_suffix}",
                "preferred_name": f"pytest audit child {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    add_resp = await admin_client.post(
        f"/api/v1/substances/{code}/xrefs",
        json={
            "xref_type": "INN",
            "xref_value": f"testinn{unique_suffix}",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201, add_resp.text

    logs_resp = await admin_client.get(
        f"/api/v1/substances/{code}/audit-logs",
        params={"include_children": True, "page_size": 50},
    )
    assert logs_resp.status_code == 200
    items = logs_resp.json()["data"]

    xref_creates = [
        it for it in items
        if it["entity_table"] == "substance_xref" and it["action"] == "CREATE"
    ]
    assert xref_creates, "应至少有一条 substance_xref CREATE 审计"
    assert all(it["entity_code"] == code for it in xref_creates), (
        f"子表 entity_code 应回填为父 substance_code={code}，实际：{[it['entity_code'] for it in xref_creates]}"
    )


@pytest.mark.asyncio
async def test_change_history_skips_updated_by(admin_client, unique_suffix):
    """UPDATE substance 后 change_history 不应包含 updated_by（audit_log.user_id 已覆盖）"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-CH-{unique_suffix}",
                "preferred_name": f"pytest change history {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    # 触发一次有意义的更新
    resp = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 1, "change_reason": "trigger update audit", "target": "PD-L1"},
    )
    assert resp.status_code == 200

    logs_resp = await admin_client.get(
        f"/api/v1/substances/{code}/audit-logs",
        params={"include_children": False, "page_size": 20},
    )
    items = logs_resp.json()["data"]
    update_logs = [it for it in items if it["action"] == "UPDATE"]
    assert update_logs, "应至少有一条 UPDATE 审计"

    for log in update_logs:
        changes = log.get("changes") or []
        fields = [c["field_name"] for c in changes]
        assert "updated_by" not in fields, (
            f"change_history 不应记录 updated_by，实际记录了：{fields}"
        )
        assert "updated_at" not in fields
        assert "version" not in fields


@pytest.mark.asyncio
async def test_list_substances_batches_xref_load(admin_client, unique_suffix):
    """N+1 修复回归：列表对每个 substance 的 INN 都能正确读出（验证批量加载逻辑正确）"""
    created_codes: list[str] = []
    for i in range(3):
        code = (
            await admin_client.post(
                "/api/v1/substances",
                json={
                    "substance_type": "mab",
                    "internal_code": f"TEST-BATCH-{unique_suffix}-{i}",
                    "preferred_name": f"pytest batch {unique_suffix} {i}",
                },
            )
        ).json()["data"]["substance_code"]
        created_codes.append(code)
        await admin_client.post(
            f"/api/v1/substances/{code}/xrefs",
            json={
                "xref_type": "INN",
                "xref_value": f"batchinn{unique_suffix}{i}",
                "is_primary": True,
            },
        )

    list_resp = await admin_client.get(
        "/api/v1/substances", params={"q": unique_suffix, "page_size": 50}
    )
    items = list_resp.json()["data"]
    by_code = {it["substance_code"]: it for it in items}
    for i, code in enumerate(created_codes):
        assert code in by_code, f"列表应包含 {code}"
        assert by_code[code]["inn"] == f"batchinn{unique_suffix}{i}", (
            f"INN 应为 batchinn{unique_suffix}{i}，实际 {by_code[code]['inn']}"
        )
