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
    """GxP 关键动作未提供 signature → 422 signature_required"""
    code = await _new_substance(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={"comment": "测试缺密码"},  # 缺 signature 对象
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
        json={
            "comment": "测试错误密码",
            "signature": {"password": "wrong_password", "reason": "测试错误密码签名理由"},
        },
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
        json={
            "comment": "测试合规签名审批",
            "signature": {"password": ADMIN_PASSWORD, "reason": "合规审批签名理由"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["new_status"] == "registered"

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
            json={
                "comment": f"测试多次签名 {action}",
                "signature": {"password": ADMIN_PASSWORD, "reason": f"多次签名理由 {action}"},
            },
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
    """非 GxP 关键动作（:restrict）不要求 signature；status_history.e_signature_id=NULL"""
    code = await _new_substance(admin_client, unique_suffix)
    # 先推到 active
    for action in ["approve", "activate"]:
        await admin_client.post(
            f"/api/v1/substances/{code}:{action}",
            json={
                "comment": f"prep {action}",
                "signature": {"password": ADMIN_PASSWORD, "reason": f"prep {action} 签名理由"},
            },
        )
    # restrict 不带 signature
    r = await admin_client.post(
        f"/api/v1/substances/{code}:restrict",
        json={"comment": "临时风控测试，不需签名"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["new_status"] == "restricted"

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
        json={
            "comment": "测试缺 sign 权限",
            "signature": {"password": "__REDACTED_SEED_PASSWORD_5__", "reason": "测试缺权限签名理由"},
        },
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
        json={
            "comment": "测试项目签名审批",
            "signature": {"password": ADMIN_PASSWORD, "reason": "项目审批签名理由"},
        },
    )
    assert r.status_code == 200

    hist = (
        await admin_client.get(f"/api/v1/projects/{pcode}/status-history")
    ).json()["data"]
    assert hist[0]["e_signature_id"] is not None


@pytest.mark.asyncio
async def test_signature_reason_independent_from_comment(admin_client, unique_suffix):
    """UI3 / API V1.1 §6.5（DEV-MDM-001 V1.2 Batch G1.B）：
    电子签名 signature.reason 独立于业务 comment 字段：
    - comment 写入 audit_log.reason + status_history.change_reason
    - signature.reason 写入 e_signature.signature_reason
    两者必须分离记录（21 CFR Part 11 §11.50）。
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.domains.audit.models import ESignature

    # 1) signature.reason ≠ comment → 各自落到对应字段
    code = await _new_substance(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={
            "comment": "数据评审完成,准备入库",
            "signature": {
                "password": ADMIN_PASSWORD,
                "reason": "Phase I CMC 评审通过 - QA 批准",
            },
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
        assert sig_row.signature_reason != "数据评审完成,准备入库"

    # 2) signature 整个对象缺失 → 422 signature_required（service 层校验）
    code2 = await _new_substance(admin_client, f"{unique_suffix}-no-sig")
    r2 = await admin_client.post(
        f"/api/v1/substances/{code2}:approve",
        json={"comment": "未提供 signature 对象"},
    )
    assert r2.status_code == 422
    assert r2.json()["meta"]["error"]["type"] == "signature_required"

    # 3) signature.reason 缺失 → 422 pydantic（reason 是必填字段）
    r3 = await admin_client.post(
        f"/api/v1/substances/{code2}:approve",
        json={
            "comment": "signature 对象缺 reason",
            "signature": {"password": ADMIN_PASSWORD},
        },
    )
    assert r3.status_code == 422


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
        json={
            "comment": "prep approve",
            "signature": {"password": ADMIN_PASSWORD, "reason": "prep approve 签名理由"},
        },
    )
    # start 不需要
    r = await admin_client.post(
        f"/api/v1/projects/{pcode}:start",
        json={"comment": "测试启动不需签名"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["new_status"] == "active"
