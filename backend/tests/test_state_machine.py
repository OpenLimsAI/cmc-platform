"""
Substance 状态机端点测试
"""
import pytest


async def _create(client, unique_suffix: str) -> str:
    resp = await client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-SM-{unique_suffix}",
            "preferred_name": "pytest state machine",
        },
    )
    return resp.json()["data"]["substance_code"]


# GxP 关键动作（approve / activate / deprecate / obsolete）需电子签名 → 带 admin 密码
SIGNATURE_REQUIRED = {"approve", "activate", "deprecate", "obsolete"}
ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _change(
    client,
    code: str,
    action: str,
    reason: str = "test reason ≥ 5",
    password: str | None = None,
    signature_reason: str | None = None,
):
    # API-MDM-001 V1.1 §6.5：comment + signature 嵌套
    body: dict = {"comment": reason}
    if action in SIGNATURE_REQUIRED:
        body["signature"] = {
            "password": password or ADMIN_PASSWORD,
            "reason": signature_reason or f"pytest 签名理由 - {action}",
        }
    return await client.post(
        f"/api/v1/substances/{code}:{action}",
        json=body,
    )


@pytest.mark.asyncio
async def test_full_lifecycle(admin_client, unique_suffix):
    code = await _create(admin_client, unique_suffix)

    for action, expected in [
        ("approve", "registered"),
        ("activate", "active"),
        ("deprecate", "deprecated"),
        ("obsolete", "obsoleted"),
    ]:
        r = await _change(admin_client, code, action)
        assert r.status_code == 200, f"{action} 失败: {r.status_code} {r.text}"
        actual = r.json()["data"]["new_status"]
        assert actual == expected, (
            f"{action}: got {actual}, expected {expected}. "
            f"Full body: {r.text}"
        )
        # 二次确认：用 GET 端点重读
        detail = (await admin_client.get(f"/api/v1/substances/{code}")).json()["data"]
        assert detail["status"] == expected, (
            f"{action}: server returned {actual} but GET shows {detail['status']}"
        )


@pytest.mark.asyncio
async def test_invalid_transition_rejected(admin_client, unique_suffix):
    """draft 不能直接 obsolete"""
    code = await _create(admin_client, unique_suffix)
    r = await _change(admin_client, code, "obsolete")
    assert r.status_code == 422
    assert r.json()["code"] == 42201
    assert r.json()["meta"]["error"]["type"] == "state_invalid"


@pytest.mark.asyncio
async def test_reason_too_short(admin_client, unique_suffix):
    """pydantic 应在 reason < 5 字时拦下"""
    code = await _create(admin_client, unique_suffix)
    r = await _change(admin_client, code, "approve", reason="hi")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_restrict_then_deprecate(admin_client, unique_suffix):
    """active → restricted → deprecated 路径"""
    code = await _create(admin_client, unique_suffix)
    await _change(admin_client, code, "approve")
    await _change(admin_client, code, "activate")
    assert (await _change(admin_client, code, "restrict")).json()["data"]["new_status"] == "restricted"
    assert (await _change(admin_client, code, "deprecate")).json()["data"]["new_status"] == "deprecated"


@pytest.mark.asyncio
async def test_status_history_recorded(admin_client, unique_suffix):
    code = await _create(admin_client, unique_suffix)
    await _change(admin_client, code, "approve", reason="批准注册测试历史记录")
    await _change(admin_client, code, "activate", reason="激活进入生产")

    r = await admin_client.get(f"/api/v1/substances/{code}/status-history")
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 2
    # 倒序：最新的在前
    assert items[0]["new_status"] == "active"
    assert items[1]["new_status"] == "registered"
    # S8（DEV-MDM-001 V1.2 / migration 0028）：change_reason 由 service 后置 UPDATE 回填
    # 触发器只写字面量 'status changed'，service 必须把每条 history 的 reason 改成实际值
    assert items[0]["change_reason"] == "激活进入生产"
    assert items[1]["change_reason"] == "批准注册测试历史记录"
    for item in items:
        assert item["change_reason"] != "status changed", (
            "service 应已把触发器写入的占位 'status changed' 改为实际 reason"
        )
