"""
Equipment CRUD 关键路径测试（EQP 设备主数据域）

eqp.equipment（0040_eqp_equipment）：
  - equipment_code: 留空自动生成 EQP-yyyyXXXXXX；也可手动传入沿用历史编号
  - category: 分析仪器 / 工艺制备设备 / 通用实验室设备 / 公用工程环境支持 / IT自动化数据系统（5 类）
  - status: active/retired（主数据状态）
  - equipment_status: enabled/sealed/scrapped（设备状态，由 MDM 管理）
  - 软删除需 change_reason ≥5 字符
"""
import pytest


@pytest.mark.asyncio
async def test_create_equipment_auto_code(admin_client, unique_suffix):
    """留空 equipment_code 自动生成 EQP- 年度序列编码"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 液相 {unique_suffix}",
            "category": "分析仪器",
            "model": "LC-2030C",
            "manufacturer": "Shimadzu",
            "serial_no": f"SN-{unique_suffix}",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["equipment_code"].startswith("EQP-")
    assert data["status"] == "active"
    assert data["equipment_status"] == "enabled"
    assert data["category"] == "分析仪器"
    assert resp.headers.get("Location") == f"/api/v1/equipments/{data['equipment_code']}"


@pytest.mark.asyncio
async def test_create_equipment_new_fields_roundtrip(admin_client, unique_suffix):
    """设备扩展字段及出厂日期创建→详情→更新往返。"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 培养箱 {unique_suffix}",
            "category": "通用实验室设备",
            "rated_power": "1500W",
            "total_weight": 85.5,
            "origin": "德国",
            "manufacture_date": "2024-06-15",
            "description": "温度范围 5-50℃，CO2 0-20%",
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["equipment_code"]
    d = resp.json()["data"]
    assert d["rated_power"] == "1500W"
    assert d["total_weight"] == 85.5
    assert d["origin"] == "德国"
    assert d["manufacture_date"] == "2024-06-15"
    assert d["description"] == "温度范围 5-50℃，CO2 0-20%"

    got = (await admin_client.get(f"/api/v1/equipments/{code}")).json()["data"]
    assert got["rated_power"] == "1500W"
    assert got["total_weight"] == 85.5
    assert got["origin"] == "德国"
    assert got["manufacture_date"] == "2024-06-15"

    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"rated_power": "220V/50Hz/2kW", "change_reason": "校准额定功率"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["rated_power"] == "220V/50Hz/2kW"
    assert upd.json()["data"]["origin"] == "德国"  # 未传不变


@pytest.mark.asyncio
async def test_create_equipment_with_workstation(admin_client, unique_suffix):
    """附带专用工作站：has_workstation + workstation_info JSONB 往返"""
    ws = {
        "brand": "Dell",
        "model": "OptiPlex 7090",
        "serial": f"WS-{unique_suffix}",
        "os": "Windows 10 LTSC",
        "cpu": "i7-11700",
        "gpu": "UHD 750",
        "ram": "32GB",
        "disk": "1TB SSD",
        "monitor_brand": "Dell",
        "monitor_model": "P2422H",
        "monitor_serial": f"MON-{unique_suffix}",
    }
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest HPLC 带工作站 {unique_suffix}",
            "category": "分析仪器",
            "has_workstation": True,
            "workstation_info": ws,
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["equipment_code"]
    d = resp.json()["data"]
    assert d["has_workstation"] is True
    assert d["workstation_info"]["cpu"] == "i7-11700"

    got = (await admin_client.get(f"/api/v1/equipments/{code}")).json()["data"]
    assert got["workstation_info"]["os"] == "Windows 10 LTSC"
    assert got["workstation_info"]["monitor_serial"] == f"MON-{unique_suffix}"

    # 取消勾选 → 清空配置
    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"has_workstation": False, "workstation_info": None,
              "change_reason": "拆除专用工作站"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["has_workstation"] is False
    assert upd.json()["data"]["workstation_info"] is None


@pytest.mark.asyncio
async def test_equipment_id_always_auto_no_manual(admin_client, unique_suffix):
    """设备ID 一律系统生成：即使前端误传 equipment_code 也被忽略, 不沿用"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_code": "SHOULD-BE-IGNORED",  # 不在 schema 内, 被忽略
            "equipment_name": f"pytest 天平 {unique_suffix}",
            "category": "通用实验室设备",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["equipment_code"].startswith("EQP-")


@pytest.mark.asyncio
async def test_equipment_no_and_fixed_asset_no_roundtrip(admin_client, unique_suffix):
    """设备编号(业务) + 固资编号 创建→详情→更新 往返；设备ID 仍自动"""
    no = f"QC-{unique_suffix[:6]}"
    fa = f"ZJSW-{unique_suffix[:6]}"
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_no": no,
            "fixed_asset_no": fa,
            "equipment_name": f"pytest 编号 {unique_suffix}",
            "category": "通用实验室设备",
        },
    )
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert d["equipment_code"].startswith("EQP-")
    assert d["equipment_no"] == no
    assert d["fixed_asset_no"] == fa
    code = d["equipment_code"]

    got = (await admin_client.get(f"/api/v1/equipments/{code}")).json()["data"]
    assert got["equipment_no"] == no and got["fixed_asset_no"] == fa

    # q 搜索可按设备编号命中
    lst = (await admin_client.get(f"/api/v1/equipments?q={no}")).json()
    assert any(it["equipment_no"] == no for it in lst["data"])

    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"equipment_no": f"{no}-R", "change_reason": "更正业务编号"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["equipment_no"] == f"{no}-R"


@pytest.mark.asyncio
async def test_create_equipment_invalid_category_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest bad cat {unique_suffix}",
            "category": "不存在的分类",
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_update_delete_equipment(admin_client, unique_suffix):
    """详情 → 更新(含 change_reason) → 软删除 → 404"""
    create = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest lifecycle {unique_suffix}",
            "category": "公用工程/环境与支持系统",
        },
    )
    assert create.status_code == 201, create.text
    code = create.json()["data"]["equipment_code"]

    # 详情
    got = await admin_client.get(f"/api/v1/equipments/{code}")
    assert got.status_code == 200, got.text
    assert got.json()["data"]["equipment_code"] == code

    # 更新
    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={
            "manufacturer": "Mettler Toledo",
            "status": "retired",
            "change_reason": "pytest 更新测试",
        },
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["manufacturer"] == "Mettler Toledo"
    assert upd.json()["data"]["status"] == "retired"

    # 软删除（change_reason 必填 ≥5）
    short = await admin_client.delete(
        f"/api/v1/equipments/{code}", json={"change_reason": "短"}
    )
    assert short.status_code == 400, short.text

    deleted = await admin_client.delete(
        f"/api/v1/equipments/{code}", json={"change_reason": "pytest 清理测试数据"}
    )
    assert deleted.status_code == 204, deleted.text

    gone = await admin_client.get(f"/api/v1/equipments/{code}")
    assert gone.status_code == 404, gone.text


@pytest.mark.asyncio
async def test_equipment_status_managed_in_mdm_with_audit_reason(admin_client, unique_suffix):
    """设备状态三值均由 MDM 更新；实际变更状态时必须填写审计原因。"""
    create = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest status {unique_suffix}",
            "category": "通用实验室设备",
        },
    )
    assert create.status_code == 201, create.text
    code = create.json()["data"]["equipment_code"]
    assert create.json()["data"]["status"] == "active"
    assert create.json()["data"]["equipment_status"] == "enabled"

    missing_reason = await admin_client.put(
        f"/api/v1/equipments/{code}", json={"equipment_status": "sealed"}
    )
    assert missing_reason.status_code == 400, missing_reason.text
    assert "变更原因" in missing_reason.text

    sealed = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"equipment_status": "sealed", "change_reason": "设备暂停使用并封存"},
    )
    assert sealed.status_code == 200, sealed.text
    assert sealed.json()["data"]["status"] == "active"
    assert sealed.json()["data"]["equipment_status"] == "sealed"

    listed = await admin_client.get(
        "/api/v1/equipments", params={"equipment_status": "sealed"}
    )
    assert listed.status_code == 200, listed.text
    assert any(row["equipment_code"] == code for row in listed.json()["data"])

    scrapped = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"equipment_status": "scrapped", "change_reason": "设备完成审批并正式报废"},
    )
    assert scrapped.status_code == 200, scrapped.text
    assert scrapped.json()["data"]["equipment_status"] == "scrapped"

    legacy = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"equipment_status": "retired", "change_reason": "验证非法设备状态"},
    )
    assert legacy.status_code == 400, legacy.text


@pytest.mark.asyncio
async def test_equipment_list_filter(admin_client, unique_suffix):
    """关键词 + 分类筛选"""
    name = f"pytest filter {unique_suffix}"
    await admin_client.post(
        "/api/v1/equipments",
        json={"equipment_name": name, "category": "分析仪器"},
    )
    resp = await admin_client.get(
        "/api/v1/equipments", params={"q": unique_suffix, "category": "分析仪器"}
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert any(i["equipment_name"] == name for i in items)


@pytest.mark.asyncio
async def test_equipment_readonly_cannot_write(readonly_client, unique_suffix):
    """READ_ONLY_USER 有 equipment:read 无 equipment:create"""
    listed = await readonly_client.get("/api/v1/equipments")
    assert listed.status_code == 200, listed.text

    resp = await readonly_client.post(
        "/api/v1/equipments",
        json={"equipment_name": f"pytest forbidden {unique_suffix}", "category": "通用实验室设备"},
    )
    assert resp.status_code == 403, resp.text


# ============== 公司级设备清单治理字段（0057，2026-09-10）==============

@pytest.mark.asyncio
async def test_equipment_governance_fields_roundtrip(admin_client, unique_suffix):
    """使用部门 / 厂区 / 房间 / 分级 / 分级依据 / 首次启用日期 创建→详情→更新 往返"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 生物反应器 {unique_suffix}",
            "category": "工艺/制备设备",
            "department": "生产一部",
            "site": "南楼",
            "room": "3129培养间",
            "criticality": "关键",
            "criticality_basis": "直接接触产品",
            "commission_date": "2016-05-01",
        },
    )
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    code = d["equipment_code"]
    assert d["department"] == "生产一部"
    assert d["site"] == "南楼"
    assert d["room"] == "3129培养间"
    assert d["criticality"] == "关键"
    assert d["commission_date"] == "2016-05-01"

    got = (await admin_client.get(f"/api/v1/equipments/{code}")).json()["data"]
    assert got["criticality_basis"] == "直接接触产品"

    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"criticality": "一般", "change_reason": "复评后降级"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["criticality"] == "一般"
    assert upd.json()["data"]["department"] == "生产一部"  # 未传不变


@pytest.mark.asyncio
async def test_equipment_criticality_dictionary_follows_category(admin_client, unique_suffix):
    """分级字典跟分类走：分析仪器 A/B/C，其他分类 关键/一般，串用要被拒"""
    # 分析仪器用 A/B/C
    ok = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 液相 {unique_suffix}",
            "category": "分析仪器",
            "criticality": "A",
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["criticality"] == "A"

    # 分析仪器不能用「关键」（请求体校验失败 → 40001/400）
    bad = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 液相2 {unique_suffix}",
            "category": "分析仪器",
            "criticality": "关键",
        },
    )
    assert bad.status_code == 400, bad.text
    assert "A/B/C" in bad.text

    # 生产设备不能用 A
    bad2 = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 反应器2 {unique_suffix}",
            "category": "工艺/制备设备",
            "criticality": "A",
        },
    )
    assert bad2.status_code == 400, bad2.text
    assert "关键/一般" in bad2.text


@pytest.mark.asyncio
async def test_equipment_criticality_rejected_when_category_changes(admin_client, unique_suffix):
    """把分析仪器改成生产设备时，原 A 级分级不再合法 → 400，提示一并调整"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 待改分类 {unique_suffix}",
            "category": "分析仪器",
            "criticality": "B",
        },
    )
    code = resp.json()["data"]["equipment_code"]

    bad = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={"category": "工艺/制备设备", "change_reason": "重新界定为生产设备"},
    )
    assert bad.status_code == 400, bad.text

    # 分类和分级一起改则通过
    ok = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={
            "category": "工艺/制备设备",
            "criticality": "关键",
            "change_reason": "重新界定为生产设备并定级",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["criticality"] == "关键"


@pytest.mark.asyncio
async def test_equipment_list_filter_by_department_and_criticality(admin_client, unique_suffix):
    """列表按使用部门 / 分级过滤"""
    dept = f"pytest部门{unique_suffix}"
    await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 部门过滤 {unique_suffix}",
            "category": "工艺/制备设备",
            "department": dept,
            "criticality": "关键",
        },
    )
    resp = await admin_client.get(
        "/api/v1/equipments", params={"department": dept, "criticality": "关键"}
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["department"] == dept
    assert items[0]["criticality"] == "关键"


# ============ 别名/曾用名（migration 0059）============
@pytest.mark.asyncio
async def test_alias_create_update_and_search(admin_client, unique_suffix):
    """别名是正式字段：能建、能改、能按旧称搜到"""
    name = f"别名测试设备{unique_suffix}"
    old_name = f"BR-OLD-{unique_suffix}"
    r = await admin_client.post("/api/v1/equipments", json={
        "equipment_name": name, "category": "工艺/制备设备",
        "alias": f"{old_name};发酵线9",
    })
    assert r.status_code == 201, r.text
    code = r.json()["data"]["equipment_code"]
    assert r.json()["data"]["alias"] == f"{old_name};发酵线9"

    # 按旧称搜得到
    r = await admin_client.get(f"/api/v1/equipments?q={old_name}")
    assert r.status_code == 200
    assert code in {e["equipment_code"] for e in r.json()["data"]}

    # 可改；改完按新旧称分别验证
    r = await admin_client.put(f"/api/v1/equipments/{code}", json={"alias": "只剩一个旧称"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["alias"] == "只剩一个旧称"
    r = await admin_client.get(f"/api/v1/equipments?q={old_name}")
    assert code not in {e["equipment_code"] for e in r.json()["data"]}
