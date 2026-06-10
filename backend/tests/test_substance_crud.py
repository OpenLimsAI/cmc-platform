"""
Substance CRUD 关键路径测试
"""
import pytest


@pytest.mark.asyncio
async def test_create_substance_returns_code(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-CRUD-{unique_suffix}",
            "preferred_name": f"pytest crud {unique_suffix}",
            "confidentiality": "internal",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["substance_code"].startswith("SUB-")
    assert body["data"]["status"] == "draft"
    assert body["data"]["version"] == 1
    # API5（V1.1 §6.2 行 971-972 / Batch G3.A）：POST 创建必须设 Location 头
    code = body["data"]["substance_code"]
    assert resp.headers.get("location") == f"/api/v1/substances/{code}"


@pytest.mark.asyncio
async def test_get_substance_after_create(admin_client, unique_suffix):
    create_resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "small_molecule",
            "internal_code": f"TEST-GET-{unique_suffix}",
            "preferred_name": "pytest get",
        },
    )
    code = create_resp.json()["data"]["substance_code"]

    get_resp = await admin_client.get(f"/api/v1/substances/{code}")
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["substance_code"] == code
    assert data["internal_code"] == f"TEST-GET-{unique_suffix}"
    assert data["substance_type"] == "small_molecule"


@pytest.mark.asyncio
async def test_update_increments_version_exactly_one(admin_client, unique_suffix):
    """核心防回归：触发器自增 version，service 层不再 +=1，否则会变 +2"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-VER-{unique_suffix}",
                "preferred_name": "pytest version",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 1, "change_reason": "测试 version 自增", "target": "PD-L1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["version"] == 2
    assert resp.json()["data"]["target"] == "PD-L1"


@pytest.mark.asyncio
async def test_optimistic_lock_conflict(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-LOCK-{unique_suffix}",
                "preferred_name": "pytest lock",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 99, "target": "should-fail"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40904
    assert resp.json()["meta"]["error"]["type"] == "version_conflict"


@pytest.mark.asyncio
async def test_duplicate_internal_code_rejected(admin_client, unique_suffix):
    ic = f"TEST-DUP-{unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={"substance_type": "mab", "internal_code": ic, "preferred_name": "first"},
    )
    resp = await admin_client.post(
        "/api/v1/substances",
        json={"substance_type": "mab", "internal_code": ic, "preferred_name": "second"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40902


@pytest.mark.asyncio
async def test_internal_code_reusable_after_soft_delete(admin_client, unique_suffix):
    """H-08 策略 B：软删后 internal_code 可被新建物质复用（0045 partial unique）"""
    ic = f"TEST-REUSE-{unique_suffix}"
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={"substance_type": "mab", "internal_code": ic, "preferred_name": "first"},
        )
    ).json()["data"]["substance_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "pytest H-08 软删后复用回归"},
    )
    assert del_resp.status_code == 204

    # 复用已软删的 internal_code：应 201 而非 500/409
    reuse = await admin_client.post(
        "/api/v1/substances",
        json={"substance_type": "mab", "internal_code": ic, "preferred_name": "second"},
    )
    assert reuse.status_code == 201, reuse.text
    assert reuse.json()["data"]["internal_code"] == ic


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-DEL-{unique_suffix}",
                "preferred_name": f"pytest delete {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "pytest 软删除回归测试"},
    )
    assert del_resp.status_code == 204

    # 软删后 GET 应 404
    get_resp = await admin_client.get(f"/api/v1/substances/{code}")
    assert get_resp.status_code == 404

    # 列表过滤也不应该出现
    list_resp = await admin_client.get(
        "/api/v1/substances", params={"q": unique_suffix}
    )
    items = list_resp.json()["data"]
    assert all(it["substance_code"] != code for it in items)


@pytest.mark.asyncio
async def test_create_with_extended_protein_fields(admin_client, unique_suffix):
    """S11（DM-MDM-001 V1.1 §7.3）：protein 扩展字段 expression_vector / pi_theoretical /
    extinction_coefficient 等可经 API 写入并回读。
    """
    resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-PROT-{unique_suffix}",
            "preferred_name": "pytest protein ext",
            "protein": {
                "isotype": "IgG1",
                "expression_system": "CHO",
                "cell_line": "CHO-K1",
                "expression_vector": "pCAG-Hyg-mAb",
                "molecular_weight_da": 148000.5,
                "pi_theoretical": 8.45,
                "extinction_coefficient": 215000,
                "heavy_chain_sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMS",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["substance_code"]

    get_resp = await admin_client.get(f"/api/v1/substances/{code}?expand=protein")
    p = get_resp.json()["data"]["protein"]
    assert p["expression_vector"] == "pCAG-Hyg-mAb"
    assert p["pi_theoretical"] == 8.45
    assert p["extinction_coefficient"] == 215000
    # DB 触发器自动算 hash + length（migration 0021）
    assert p["sequence_hash_hc"] and len(p["sequence_hash_hc"]) == 64
    assert p["sequence_length_hc"] == len(
        "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMS"
    )


@pytest.mark.asyncio
async def test_xref_effective_expiry_dates(admin_client, unique_suffix):
    """S10（DM-MDM-001 V1.1 §7.6）：xref 的 effective_date / expiry_date 可写可读，
    用于按申报有效期管理 INN/CAS 等外部标识。
    """
    create_resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-XREF-DT-{unique_suffix}",
            "preferred_name": "pytest xref dates",
            "xrefs": [
                {
                    "xref_type": "INN",
                    "xref_value": f"pytestmab-{unique_suffix}",
                    "is_primary": True,
                    "effective_date": "2024-03-01",
                    "expiry_date": "2034-03-01",
                }
            ],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    code = create_resp.json()["data"]["substance_code"]

    detail = (await admin_client.get(f"/api/v1/substances/{code}?expand=xrefs")).json()["data"]
    xref = detail["xrefs"][0]
    assert xref["effective_date"] == "2024-03-01"
    assert xref["expiry_date"] == "2034-03-01"

    # PUT 更新 expiry_date
    xref_id = xref["xref_id"]
    put_resp = await admin_client.put(
        f"/api/v1/substances/{code}/xrefs/{xref_id}",
        json={"expiry_date": "2040-12-31"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["data"]["expiry_date"] == "2040-12-31"
    # 未传的字段应保持原值
    assert put_resp.json()["data"]["effective_date"] == "2024-03-01"


@pytest.mark.asyncio
async def test_put_protein_independent_endpoint(admin_client, unique_suffix):
    """API13:A（V1.2 评审 / V1.1 §5.1.3 行 750）：PUT /substances/{code}/protein 独立写端点"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-PUT-PROT-{unique_suffix}",
                "preferred_name": f"pytest put protein {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{code}/protein",
        json={
            "isotype": "IgG1",
            "expression_system": "CHO",
            "molecular_weight_da": 150000.0,
            "heavy_chain_sequence": "EVQLVESGGGLVQPGGSLRLSC",
        },
    )
    assert resp.status_code == 200, resp.text
    p = resp.json()["data"]["protein"]
    assert p["isotype"] == "IgG1"
    assert p["sequence_length_hc"] == 22

    # small_molecule 类型应被拒
    sm_code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "small_molecule",
                "internal_code": f"TEST-PUT-SM-{unique_suffix}",
                "preferred_name": "sm",
            },
        )
    ).json()["data"]["substance_code"]
    r2 = await admin_client.put(
        f"/api/v1/substances/{sm_code}/protein",
        json={"isotype": "IgG1"},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_put_adc_independent_endpoint(admin_client, unique_suffix):
    """API13:A：PUT /substances/{code}/adc 独立写端点；父子 substance_code 解析"""
    # 准备 ADC + antibody 两个 substance
    adc_code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "adc",
                "internal_code": f"TEST-PUT-ADC-{unique_suffix}",
                "preferred_name": f"pytest adc {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]
    ab_code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AB-{unique_suffix}",
                "preferred_name": f"pytest ab {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]
    payload_code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "small_molecule",
                "internal_code": f"TEST-PL-{unique_suffix}",
                "preferred_name": "payload",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{adc_code}/adc",
        json={
            "antibody_substance_code": ab_code,
            "payload_substance_code": payload_code,
            "dar_average": 4.0,
            "dar_method": "HIC",
            "conjugation_chemistry": "maleimide-thiol",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["dar_average"] == 4.0
    assert data["antibody_substance_id"] is not None
    assert data["payload_substance_id"] is not None

    # mab 类型应被拒
    r2 = await admin_client.put(
        f"/api/v1/substances/{ab_code}/adc",
        json={"dar_average": 4.0},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_lookups_endpoint(admin_client):
    """API11:B 部分立即做：GET /api/v1/lookups/{type} 从 meta.lookup_value 读"""
    resp = await admin_client.get("/api/v1/lookups/substance_status")
    assert resp.status_code == 200
    items = resp.json()["data"]
    codes = {it["code"] for it in items}
    # M3.11 seed 至少含 6 个 substance_status 项
    assert {"draft", "registered", "active", "deprecated"} <= codes
    # 按 sort_order 升序
    sort_orders = [it["sort_order"] for it in items]
    assert sort_orders == sorted(sort_orders)


@pytest.mark.asyncio
async def test_system_info_endpoint(admin_client):
    """API11:B 部分立即做：GET /api/v1/system/info"""
    resp = await admin_client.get("/api/v1/system/info")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["database"] == "ok"
    assert "app" in data
    assert "version" in data
    assert "config_summary" in data
    # is_sensitive=FALSE 的几个公开 config 应在 summary 里
    assert "password.min_length" in data["config_summary"]


@pytest.mark.asyncio
async def test_soft_delete_requires_reason(admin_client, unique_suffix):
    """M2.0：DELETE 必须带 change_reason body（21 CFR Part 11 §11.10）"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-DEL-RSN-{unique_suffix}",
                "preferred_name": f"pytest delete reason {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    # 缺 body / reason 太短 → V1.1 §4.1 validation_failed → 400
    resp = await admin_client.delete(f"/api/v1/substances/{code}")
    assert resp.status_code == 400

    resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "no"},
    )
    assert resp.status_code == 400

    # 合法 reason
    resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "符合长度要求的理由"},
    )
    assert resp.status_code == 204
