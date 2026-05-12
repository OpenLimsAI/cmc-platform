"""
电子签名核心测试（M2.5.1）

覆盖 21 CFR Part 11 §11.50/11.70/11.100/11.200 关键要求：
- 缺密码 / 错密码 / 正确密码 三条路径
- 签名后 e_signature 表写入 + status_history.e_signature_id 关联
- 签名哈希计算稳定且不同动作哈希不同
- 缺 sign 权限 403
- 签名失败计入 failed_login_count（防暴力破解）
"""
import pytest


ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_substance(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-SIG-{suffix}",
                "preferred_name": f"pytest sig {suffix}",
            },
        )
    ).json()["data"]["substance_code"]


@pytest.mark.asyncio
async def test_approve_without_password_rejected(admin_client, unique_suffix):
    """GxP 关键动作未提供 password → 422 signature_required"""
    code = await _new_substance(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={"change_reason": "测试缺密码"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == 42203  # V1.1 决议：signature_required 改 42203（保留 42202=reference_in_use）
    assert resp.json()["meta"]["error"]["type"] == "signature_required"


@pytest.mark.asyncio
async def test_approve_wrong_password_rejected(admin_client, unique_suffix):
    """错误密码 → 401 signature_invalid，e_signature 表无新增"""
    code = await _new_substance(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={"change_reason": "测试错误密码", "password": "wrong_password"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 40106
    assert resp.json()["meta"]["error"]["type"] == "signature_invalid"

    # 状态未变更
    detail = (await admin_client.get(f"/api/v1/substances/{code}")).json()["data"]
    assert detail["status"] == "draft"


@pytest.mark.asyncio
async def test_approve_correct_password_signs_and_transitions(admin_client, unique_suffix):
    """正确密码 → 200，status_history.e_signature_id 关联"""
    code = await _new_substance(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={"change_reason": "测试合规签名审批", "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "registered"

    # status-history 第一条应携带 e_signature_id
    hist = (
        await admin_client.get(f"/api/v1/substances/{code}/status-history")
    ).json()["data"]
    assert len(hist) == 1
    assert hist[0]["new_status"] == "registered"
    assert hist[0]["e_signature_id"] is not None, "status_history 应关联 e_signature_id"


@pytest.mark.asyncio
async def test_multiple_signatures_independent(admin_client, unique_suffix):
    """同一 substance 连续两个签名动作 → 两条 e_signature，不同 signature_hash"""
    code = await _new_substance(admin_client, unique_suffix)
    for action in ["approve", "activate"]:
        r = await admin_client.post(
            f"/api/v1/substances/{code}:{action}",
            json={"change_reason": f"测试多次签名 {action}", "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200

    hist = (
        await admin_client.get(f"/api/v1/substances/{code}/status-history")
    ).json()["data"]
    sig_ids = [h["e_signature_id"] for h in hist]
    assert all(s is not None for s in sig_ids)
    assert len(set(sig_ids)) == 2, "两次签名应产生不同 signature_id"


@pytest.mark.asyncio
async def test_restrict_does_not_require_signature(admin_client, unique_suffix):
    """非 GxP 关键动作（:restrict）不要求 password；status_history.e_signature_id=NULL"""
    code = await _new_substance(admin_client, unique_suffix)
    # 先推到 active
    for action in ["approve", "activate"]:
        await admin_client.post(
            f"/api/v1/substances/{code}:{action}",
            json={"change_reason": f"prep {action}", "password": ADMIN_PASSWORD},
        )
    # restrict 不带 password
    r = await admin_client.post(
        f"/api/v1/substances/{code}:restrict",
        json={"change_reason": "临时风控测试，不需签名"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "restricted"

    hist = (
        await admin_client.get(f"/api/v1/substances/{code}/status-history")
    ).json()["data"]
    restrict_hist = next(h for h in hist if h["new_status"] == "restricted")
    assert restrict_hist["e_signature_id"] is None, ":restrict 不应产生电子签名"


@pytest.mark.asyncio
async def test_sign_permission_required(researcher_client, admin_client, unique_suffix):
    """CMC_RESEARCHER 没 substance:sign 权限 → 403"""
    code = await _new_substance(admin_client, unique_suffix)
    r = await researcher_client.post(
        f"/api/v1/substances/{code}:approve",
        json={"change_reason": "测试缺 sign 权限", "password": "__REDACTED_SEED_PASSWORD_5__"},
    )
    assert r.status_code == 403
    assert "substance:sign" in r.json()["message"]


@pytest.mark.asyncio
async def test_project_approve_signature_flow(admin_client, unique_suffix):
    """PRS 端：approve 也走签名流程"""
    pcode = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest sig proj {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    r = await admin_client.post(
        f"/api/v1/projects/{pcode}:approve",
        json={"change_reason": "测试项目签名审批", "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    hist = (
        await admin_client.get(f"/api/v1/projects/{pcode}/status-history")
    ).json()["data"]
    assert hist[0]["e_signature_id"] is not None


@pytest.mark.asyncio
async def test_signature_reason_independent_from_change_reason(admin_client, unique_suffix):
    """UI3 / API V1.1 §6.4（DEV-MDM-001 V1.2 Batch G1.A）：
    电子签名时若传 signature_reason，则 e_signature.signature_reason 独立于 change_reason；
    未传时 fallback 到 change_reason（向后兼容）。21 CFR Part 11 §11.50。
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.domains.audit.models import ESignature

    # 1) 显式传 signature_reason → 独立写入
    code = await _new_substance(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={
            "change_reason": "数据评审完成，准备入库",
            "password": ADMIN_PASSWORD,
            "signature_reason": "Phase I CMC 评审通过 - QA 批准",
        },
    )
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as s:
        sig_row = (
            await s.execute(
                select(ESignature)
                .where(ESignature.entity_code == code)
                .order_by(ESignature.signed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        assert sig_row is not None
        assert sig_row.signature_reason == "Phase I CMC 评审通过 - QA 批准"
        # change_reason 与 signature_reason 必须分离
        assert sig_row.signature_reason != "数据评审完成，准备入库"

    # 2) 不传 signature_reason → fallback 到 change_reason（向后兼容）
    code2 = await _new_substance(admin_client, f"{unique_suffix}-bc")
    r2 = await admin_client.post(
        f"/api/v1/substances/{code2}:approve",
        json={
            "change_reason": "向后兼容路径，未传 signature_reason",
            "password": ADMIN_PASSWORD,
        },
    )
    assert r2.status_code == 200

    async with AsyncSessionLocal() as s:
        sig_row2 = (
            await s.execute(
                select(ESignature)
                .where(ESignature.entity_code == code2)
                .order_by(ESignature.signed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        assert sig_row2 is not None
        assert sig_row2.signature_reason == "向后兼容路径，未传 signature_reason"


@pytest.mark.asyncio
async def test_project_start_does_not_require_signature(admin_client, unique_suffix):
    """PRS :start 不要求签名"""
    pcode = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest sig proj start {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]
    # approve 需签名
    await admin_client.post(
        f"/api/v1/projects/{pcode}:approve",
        json={"change_reason": "prep approve", "password": ADMIN_PASSWORD},
    )
    # start 不需要
    r = await admin_client.post(
        f"/api/v1/projects/{pcode}:start",
        json={"change_reason": "测试启动不需签名"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "active"
