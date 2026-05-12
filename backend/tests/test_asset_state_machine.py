"""
Asset 状态机 + status-history + market-id 子资源测试（M3.2）

§8.2 status ∈ {active, on_hold, terminated}；3 个动作：hold/resume/terminate。
terminate 是 GxP 关键 → 要求电子签名（M2.5.1 模式）。
"""
import pytest

ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_asset(client, suffix: str, name_suffix: str = "") -> str:
    return (
        await client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest asset sm {suffix} {name_suffix}".strip(),
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]


async def _state(client, code: str, action: str, reason: str = "pytest state test", password: str | None = None):
    body: dict = {"change_reason": reason}
    if password is not None or action == "terminate":
        body["password"] = password or ADMIN_PASSWORD
    return await client.post(f"/api/v1/assets/{code}:{action}", json=body)


# ============== 状态机 ==============
@pytest.mark.asyncio
async def test_hold_resume_roundtrip(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "hold")
    # active → hold → on_hold
    r1 = await _state(admin_client, code, "hold")
    assert r1.status_code == 200, r1.text
    assert r1.json()["data"]["status"] == "on_hold"
    # on_hold → resume → active
    r2 = await _state(admin_client, code, "resume")
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_terminate_requires_signature(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "term")
    # 缺 password
    r = await admin_client.post(
        f"/api/v1/assets/{code}:terminate",
        json={"change_reason": "pytest 缺签名"},
    )
    assert r.status_code == 422
    assert r.json()["meta"]["error"]["type"] == "signature_required"


@pytest.mark.asyncio
async def test_terminate_wrong_password_rejected(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "wrongpw")
    r = await admin_client.post(
        f"/api/v1/assets/{code}:terminate",
        json={"change_reason": "pytest 错密码", "password": "WRONG"},
    )
    assert r.status_code == 401
    assert r.json()["meta"]["error"]["type"] == "signature_invalid"
    # 状态不应变更
    detail = (await admin_client.get(f"/api/v1/assets/{code}")).json()["data"]
    assert detail["status"] == "active"


@pytest.mark.asyncio
async def test_terminate_correct_password_signs_and_transitions(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "term_ok")
    r = await _state(admin_client, code, "terminate", "pytest 正常终止")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "terminated"

    hist = (
        await admin_client.get(f"/api/v1/assets/{code}/status-history")
    ).json()["data"]
    assert len(hist) == 1
    assert hist[0]["new_status"] == "terminated"
    assert hist[0]["e_signature_id"] is not None  # 电子签名 ID 已回填


@pytest.mark.asyncio
async def test_terminate_from_on_hold(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "term_hold")
    await _state(admin_client, code, "hold")
    r = await _state(admin_client, code, "terminate", "终止暂停中的资产")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "terminated"


@pytest.mark.asyncio
async def test_resume_from_active_rejected(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "noresume")
    r = await _state(admin_client, code, "resume")
    assert r.status_code == 422
    assert r.json()["meta"]["error"]["type"] == "state_invalid"


@pytest.mark.asyncio
async def test_status_history_recorded(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "history")
    await _state(admin_client, code, "hold")
    await _state(admin_client, code, "resume")
    await _state(admin_client, code, "terminate", "pytest 历史链测试")

    hist = (
        await admin_client.get(f"/api/v1/assets/{code}/status-history")
    ).json()["data"]
    assert len(hist) == 3
    # 最新在前
    assert hist[0]["new_status"] == "terminated"
    assert hist[0]["e_signature_id"] is not None  # terminate 签名
    assert hist[1]["new_status"] == "active"
    assert hist[1]["e_signature_id"] is None  # resume 不签
    assert hist[2]["new_status"] == "on_hold"
    assert hist[2]["e_signature_id"] is None  # hold 不签


@pytest.mark.asyncio
async def test_terminate_requires_sign_permission(researcher_client, admin_client, unique_suffix):
    """researcher 没 asset:sign 权限 → 403"""
    code = await _new_asset(admin_client, unique_suffix, "perm")
    r = await researcher_client.post(
        f"/api/v1/assets/{code}:terminate",
        json={"change_reason": "pytest 缺 sign 权限", "password": "__REDACTED_SEED_PASSWORD_5__"},
    )
    assert r.status_code == 403


# ============== Market IDs ==============
@pytest.mark.asyncio
async def test_market_id_crud_roundtrip(admin_client, unique_suffix):
    code = await _new_asset(admin_client, unique_suffix, "mid")

    add = await admin_client.post(
        f"/api/v1/assets/{code}/market-ids",
        json={
            "market_code": "CN",
            "id_type": "NMPA_APPROVAL",
            "id_value": f"国药准字 S{unique_suffix}",
            "issuing_authority": "NMPA",
            "approval_date": "2026-03-15",
            "status": "approved",
        },
    )
    assert add.status_code == 201, add.text
    mid = add.json()["data"]["market_id_pk"]

    lst = await admin_client.get(f"/api/v1/assets/{code}/market-ids")
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    upd = await admin_client.put(
        f"/api/v1/assets/{code}/market-ids/{mid}",
        json={"status": "approved", "expiry_date": "2031-03-15", "change_reason": "pytest 续期"},
    )
    assert upd.status_code == 200
    assert upd.json()["data"]["expiry_date"] == "2031-03-15"

    deleted = await admin_client.delete(
        f"/api/v1/assets/{code}/market-ids/{mid}",
        json={"change_reason": "pytest 软删除"},
    )
    assert deleted.status_code == 204

    lst2 = await admin_client.get(f"/api/v1/assets/{code}/market-ids")
    assert all(it["market_id_pk"] != mid for it in lst2.json()["data"])


@pytest.mark.asyncio
async def test_market_id_duplicate_rejected(admin_client, unique_suffix):
    """同一 asset + (market_code, id_type, id_value) 唯一"""
    code = await _new_asset(admin_client, unique_suffix, "dup")
    payload = {
        "market_code": "US",
        "id_type": "NDC",
        "id_value": f"NDC-{unique_suffix}-12345",
    }
    first = await admin_client.post(f"/api/v1/assets/{code}/market-ids", json=payload)
    assert first.status_code == 201
    dup = await admin_client.post(f"/api/v1/assets/{code}/market-ids", json=payload)
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_market_id_audit_inherits_asset_code(admin_client, unique_suffix):
    """market_id audit_log.entity_code 应为父 asset_code（v2 parent_ref）"""
    code = await _new_asset(admin_client, unique_suffix, "audit")
    await admin_client.post(
        f"/api/v1/assets/{code}/market-ids",
        json={
            "market_code": "EU",
            "id_type": "EMA_PROCEDURE",
            "id_value": f"EMEA/H/C/{unique_suffix}",
        },
    )

    logs = await admin_client.get(
        f"/api/v1/assets/{code}/audit-logs",
        params={"include_children": "true", "page_size": 50},
    )
    items = logs.json()["data"]
    mid_creates = [
        it for it in items
        if it["entity_table"] == "asset_market_id" and it["action"] == "CREATE"
    ]
    assert mid_creates
    assert all(it["entity_code"] == code for it in mid_creates)
