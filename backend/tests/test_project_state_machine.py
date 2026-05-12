"""
Project 状态机 + status-history 测试（M2.2）
"""
import pytest


async def _create_project(client, suffix: str, name_suffix: str = "") -> str:
    resp = await client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest sm {suffix} {name_suffix}".strip(),
            "project_type": "cmc",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["project_code"]


# GxP 关键动作要求电子签名
SIGNATURE_REQUIRED = {"approve", "complete", "terminate"}
ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _state_post(client, code: str, action: str, reason: str):
    body: dict = {"change_reason": reason}
    if action in SIGNATURE_REQUIRED:
        body["password"] = ADMIN_PASSWORD
    return await client.post(f"/api/v1/projects/{code}:{action}", json=body)


@pytest.mark.asyncio
async def test_full_lifecycle(admin_client, unique_suffix):
    """draft → planned → active → on_hold → active → completed"""
    code = await _create_project(admin_client, unique_suffix, "lifecycle")

    # M3.0.2：state 枚举对齐 §9.2，approve 后是 initiated 不是 planned
    transitions = [
        ("approve", "initiated"),
        ("start", "active"),
        ("hold", "on_hold"),
        ("resume", "active"),
        ("complete", "completed"),
    ]
    for action, expected in transitions:
        resp = await _state_post(
            admin_client, code, action, f"pytest 状态机 {action} 推进"
        )
        assert resp.status_code == 200, f"{action} 失败: {resp.text}"
        assert resp.json()["data"]["status"] == expected, (
            f"{action} 后预期 {expected}，实际 {resp.json()['data']['status']}"
        )

    detail = (await admin_client.get(f"/api/v1/projects/{code}")).json()["data"]
    assert detail["status"] == "completed"
    # M3.0.2 移除 approved_at/by 字段（§9.2 不含），审批时间从 status_history 推断
    assert detail["actual_start_date"] is not None, "start 应回填 actual_start_date"
    assert detail["actual_end_date"] is not None, "complete 应回填 actual_end_date"


@pytest.mark.asyncio
async def test_terminate_from_any_open_state(admin_client, unique_suffix):
    """terminate 应允许从 proposed / initiated / active / on_hold 四个状态进入"""
    for from_status, prep_actions in [
        ("proposed", []),
        ("initiated", ["approve"]),
        ("active", ["approve", "start"]),
        ("on_hold", ["approve", "start", "hold"]),
    ]:
        code = await _create_project(admin_client, unique_suffix, from_status)
        for act in prep_actions:
            await _state_post(admin_client, code, act, f"pytest prep {act}")
        resp = await _state_post(
            admin_client, code, "terminate", f"pytest terminate from {from_status}"
        )
        assert resp.status_code == 200, (
            f"terminate from {from_status} 失败: {resp.text}"
        )
        assert resp.json()["data"]["status"] == "terminated"


@pytest.mark.asyncio
async def test_invalid_transition_rejected(admin_client, unique_suffix):
    """proposed 状态不能直接 start（需先 approve 到 initiated）"""
    code = await _create_project(admin_client, unique_suffix, "invalid")
    resp = await admin_client.post(
        f"/api/v1/projects/{code}:start",
        json={"change_reason": "pytest 应拒绝"},
    )
    assert resp.status_code == 422
    assert resp.json()["meta"]["error"]["type"] == "state_invalid"


@pytest.mark.asyncio
async def test_reason_too_short(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix, "short")
    resp = await admin_client.post(
        f"/api/v1/projects/{code}:approve", json={"change_reason": "no"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_status_history_recorded(admin_client, unique_suffix):
    """status-history 端点返回完整状态轨迹（最新在前）"""
    code = await _create_project(admin_client, unique_suffix, "history")
    for action in ["approve", "start", "hold"]:
        await _state_post(admin_client, code, action, f"pytest {action}")

    resp = await admin_client.get(f"/api/v1/projects/{code}/status-history")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 3
    # 最新在前
    assert items[0]["new_status"] == "on_hold"
    assert items[0]["old_status"] == "active"
    assert items[-1]["new_status"] == "initiated"  # §9.2 approve → initiated
    assert items[-1]["old_status"] == "proposed"
    assert "pytest hold" in items[0]["change_reason"]


@pytest.mark.asyncio
async def test_state_change_requires_approve_permission(
    admin_client, readonly_client, unique_suffix
):
    """READ_ONLY_USER 没 project:approve，应 403"""
    code = await _create_project(admin_client, unique_suffix, "perm")
    resp = await readonly_client.post(
        f"/api/v1/projects/{code}:approve",
        json={"change_reason": "pytest 应拒绝"},
    )
    assert resp.status_code == 403
