"""
ref.project_substance link/unlink + 反向查询测试

M3.0.1 对齐 DM-MDM-001 V1.0 §11.2：
  - 复合 PK (project_id, substance_id, relation_type)
  - relation_type ∈ {primary/secondary/reference/control/derivative}
  - 软删除字段名 deleted_at（不是 unlinked_at）
"""
import pytest


async def _new_project(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/projects",
            json={"project_name": f"pytest link {suffix}", "project_type": "cmc"},
        )
    ).json()["data"]["project_code"]


async def _new_substance(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-LK-{suffix}",
                "preferred_name": f"pytest link sub {suffix}",
            },
        )
    ).json()["data"]["substance_code"]


@pytest.mark.asyncio
async def test_link_unlink_roundtrip(admin_client, unique_suffix):
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)

    # 绑定
    link = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances",
        json={"substance_code": scode, "relation_type": "primary", "is_primary": True},
    )
    assert link.status_code == 201, link.text
    assert link.json()["data"]["substance_code"] == scode
    assert link.json()["data"]["relation_type"] == "primary"
    assert link.json()["data"]["is_primary"] is True

    # 项目→物质列表
    lst = await admin_client.get(f"/api/v1/projects/{pcode}/substances")
    assert lst.status_code == 200
    items = lst.json()["data"]
    assert len(items) == 1
    assert items[0]["substance_code"] == scode

    # 物质→项目反向查询
    rev = await admin_client.get(f"/api/v1/substances/{scode}/projects")
    assert rev.status_code == 200
    rev_items = rev.json()["data"]
    assert len(rev_items) == 1
    assert rev_items[0]["project_code"] == pcode

    # 解除：DELETE 路径用 (substance_code, relation_type) 复合键
    unlink = await admin_client.delete(
        f"/api/v1/projects/{pcode}/substances/{scode}/primary",
        json={"change_reason": "pytest 取消引用"},
    )
    assert unlink.status_code == 204, unlink.text

    # 默认不返回已取消引用
    lst2 = await admin_client.get(f"/api/v1/projects/{pcode}/substances")
    assert len(lst2.json()["data"]) == 0

    # include_deleted=true 可见
    lst3 = await admin_client.get(
        f"/api/v1/projects/{pcode}/substances",
        params={"include_deleted": "true"},
    )
    items3 = lst3.json()["data"]
    assert any(
        it["substance_code"] == scode
        and it["relation_type"] == "primary"
        and it["deleted_at"] is not None
        for it in items3
    )


@pytest.mark.asyncio
async def test_duplicate_active_relation_rejected(admin_client, unique_suffix):
    """同一 (project, substance, relation_type) 在解除前不能重复绑定"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    payload = {"substance_code": scode, "relation_type": "secondary"}

    first = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances", json=payload
    )
    assert first.status_code == 201
    dup = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances", json=payload
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_different_relation_types_can_coexist(admin_client, unique_suffix):
    """同一 (project, substance) 不同 relation_type 可并存"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    for rt in ["primary", "secondary", "reference"]:
        r = await admin_client.post(
            f"/api/v1/projects/{pcode}/substances",
            json={"substance_code": scode, "relation_type": rt},
        )
        assert r.status_code == 201, f"relation_type={rt} 失败: {r.text}"

    lst = await admin_client.get(f"/api/v1/projects/{pcode}/substances")
    assert len(lst.json()["data"]) == 3


@pytest.mark.asyncio
async def test_relink_after_unlink_restores_record(admin_client, unique_suffix):
    """取消引用后再绑定同一 relation_type，应恢复（UPDATE deleted_at=NULL）"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    payload = {"substance_code": scode, "relation_type": "control"}

    r1 = await admin_client.post(f"/api/v1/projects/{pcode}/substances", json=payload)
    assert r1.status_code == 201

    rm = await admin_client.delete(
        f"/api/v1/projects/{pcode}/substances/{scode}/control",
        json={"change_reason": "pytest 取消引用"},
    )
    assert rm.status_code == 204

    # 再绑定同 relation_type 应成功（恢复历史行）
    r2 = await admin_client.post(f"/api/v1/projects/{pcode}/substances", json=payload)
    assert r2.status_code == 201, r2.text

    # 现在应只有 1 条活动引用
    lst = await admin_client.get(f"/api/v1/projects/{pcode}/substances")
    assert len(lst.json()["data"]) == 1


@pytest.mark.asyncio
async def test_invalid_relation_type_rejected(admin_client, unique_suffix):
    """非法 relation_type 应 422"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances",
        json={"substance_code": scode, "relation_type": "primary_target"},  # 旧值
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_link_obsoleted_substance_rejected(admin_client, unique_suffix):
    """obsoleted 物质不允许新建关联"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    for action in ["approve", "activate", "deprecate", "obsolete"]:
        r = await admin_client.post(
            f"/api/v1/substances/{scode}:{action}",
            json={
                "comment": f"pytest 推 {action}",
                "signature": {"password": "__REDACTED_SEED_PASSWORD_1__", "reason": f"pytest {action} 签名理由"},
            },
        )
        assert r.status_code == 200, f"{action} 失败: {r.text}"

    resp = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances",
        json={"substance_code": scode, "relation_type": "primary"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_link_terminated_project_rejected(admin_client, unique_suffix):
    """R5（DEV-MDM-001 V1.2 / migration 0029）：terminated project 不允许新建关联，
    与 §11.1 设计原则三类禁建之一一致（substance.obsoleted / asset.terminated / project.terminated）。
    """
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    # 推到 active 然后 terminate
    for action, reason in [
        ("approve", "pytest 推 approve"),
        ("start", "pytest 推 start"),
        ("terminate", "pytest 终止 project ≥5"),
    ]:
        body: dict = {"comment": reason}
        if action in ("approve", "terminate"):
            body["signature"] = {"password": "__REDACTED_SEED_PASSWORD_1__", "reason": f"pytest {action} 签名"}
        r = await admin_client.post(f"/api/v1/projects/{pcode}:{action}", json=body)
        assert r.status_code == 200, f"{action} 失败: {r.text}"

    resp = await admin_client.post(
        f"/api/v1/projects/{pcode}/substances",
        json={"substance_code": scode, "relation_type": "primary"},
    )
    assert resp.status_code == 400
    assert "terminated" in resp.text


@pytest.mark.asyncio
async def test_link_audit_inherits_project_code(admin_client, unique_suffix):
    """ref.project_substance 触发器写 audit_log 时 entity_code 应是 project_code"""
    pcode = await _new_project(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/projects/{pcode}/substances",
        json={"substance_code": scode, "relation_type": "secondary"},
    )

    logs = await admin_client.get(
        f"/api/v1/projects/{pcode}/audit-logs",
        params={"include_children": "true", "page_size": 50},
    )
    items = logs.json()["data"]
    link_creates = [
        it for it in items
        if it["entity_table"] == "project_substance" and it["action"] == "CREATE"
    ]
    assert link_creates, "应至少一条 project_substance CREATE 审计"
    assert all(it["entity_code"] == pcode for it in link_creates), (
        f"audit entity_code 应回填为 project_code={pcode}"
    )
