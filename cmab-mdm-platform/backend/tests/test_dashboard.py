"""Phase 5.B 仪表盘聚合测试

覆盖：
- /dashboard/summary 返回 4 域 totals + 8 个分布 + 30 天趋势
- totals 与各域 list endpoint total 一致
- 分布按 group by 字段
- trend_30d 始终 30 天（即使无数据也有 0 填充）
- /dashboard/gantt 返回项目时间线 + 里程碑
- gantt 排除终止项目（默认）
- 未登录 401（不开放匿名）
- readonly 也能看（不需要 audit:read）
"""
import pytest


@pytest.mark.asyncio
async def test_summary_shape(admin_client):
    r = await admin_client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) == {"visible_domains", "totals", "distributions", "trend_30d"}
    assert set(data["visible_domains"]) == {
        "substance", "project", "asset", "material", "equipment", "target"
    }
    assert set(data["totals"].keys()) == {
        "substance", "project", "asset", "material", "equipment", "target"
    }
    # 10 个分布
    assert set(data["distributions"].keys()) == {
        "substance_by_type",
        "substance_by_status",
        "project_by_status",
        "project_by_priority",
        "asset_by_phase",
        "asset_by_status",
        "material_by_type",
        "material_by_grade",
        "equipment_by_category",
        "equipment_by_status",
        "target_by_status",
        "target_by_entry_type",
    }
    # 6 域趋势（0050 起含靶点）
    assert set(data["trend_30d"].keys()) == {
        "substance", "project", "asset", "material", "equipment", "target"
    }


@pytest.mark.asyncio
async def test_totals_match_list_endpoints(admin_client):
    """summary totals 必须与对应域 list 端点 pagination.total 一致"""
    r_sum = (await admin_client.get("/api/v1/dashboard/summary")).json()["data"]
    r_sub = (await admin_client.get("/api/v1/substances?page=1&page_size=1")).json()
    r_proj = (await admin_client.get("/api/v1/projects?page=1&page_size=1")).json()
    r_ast = (await admin_client.get("/api/v1/assets?page=1&page_size=1")).json()
    r_mat = (await admin_client.get("/api/v1/materials?page=1&page_size=1")).json()
    r_eqp = (await admin_client.get("/api/v1/equipments?page=1&page_size=1")).json()
    assert r_sum["totals"]["substance"] == r_sub["meta"]["pagination"]["total"]
    assert r_sum["totals"]["project"] == r_proj["meta"]["pagination"]["total"]
    assert r_sum["totals"]["asset"] == r_ast["meta"]["pagination"]["total"]
    assert r_sum["totals"]["material"] == r_mat["meta"]["pagination"]["total"]
    assert r_sum["totals"]["equipment"] == r_eqp["meta"]["pagination"]["total"]


@pytest.mark.asyncio
async def test_distribution_keys_and_count_sum(admin_client):
    """分布总和 == 各域 totals（覆盖所有未软删的记录）"""
    data = (await admin_client.get("/api/v1/dashboard/summary")).json()["data"]
    type_sum = sum(item["count"] for item in data["distributions"]["substance_by_type"])
    assert type_sum == data["totals"]["substance"]

    proj_sum = sum(
        item["count"] for item in data["distributions"]["project_by_status"]
    )
    assert proj_sum == data["totals"]["project"]

    asset_sum = sum(
        item["count"] for item in data["distributions"]["asset_by_phase"]
    )
    assert asset_sum == data["totals"]["asset"]


@pytest.mark.asyncio
async def test_trend_30d_always_30_days(admin_client):
    data = (await admin_client.get("/api/v1/dashboard/summary")).json()["data"]
    for entity in ("substance", "project", "asset", "material", "equipment"):
        series = data["trend_30d"][entity]
        assert len(series) == 30, f"{entity} 趋势应该恰好 30 天"
        # 每项含 date + count
        for point in series:
            assert "date" in point and "count" in point
            assert isinstance(point["count"], int)
        # 日期单调递增
        dates = [p["date"] for p in series]
        assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_summary_requires_auth(http_client):
    r = await http_client.get("/api/v1/dashboard/summary")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_summary_readonly_can_view(readonly_client):
    """readonly 没有 audit:read 也能看 dashboard（聚合数据不暴露具体记录）"""
    r = await readonly_client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_gantt_shape(admin_client):
    r = await admin_client.get("/api/v1/dashboard/gantt")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data, list)
    for proj in data:
        # 必有项目元信息
        assert "project_code" in proj
        assert "project_name" in proj
        assert "status" in proj
        # 必有 milestones 数组（可空）
        assert isinstance(proj["milestones"], list)
        # 排除 terminated（默认查询）
        assert proj["status"] != "terminated"
        # 必有至少一组时间线
        has_dates = (
            proj.get("planned_start_date")
            or proj.get("actual_start_date")
        )
        assert has_dates is not None


@pytest.mark.asyncio
async def test_gantt_requires_auth(http_client):
    r = await http_client.get("/api/v1/dashboard/gantt")
    assert r.status_code == 401


# ============ 2026-09-10：仪表盘按读权限裁剪；无读权限 403 ============
async def _login_as(http_client, username: str, password: str):
    import asyncio

    from tests.conftest import _AuthedClient

    for _ in range(10):
        r = await http_client.post("/api/v1/auth/login", json={"username": username, "password": password})
        if r.status_code == 200:
            return _AuthedClient(http_client, r.json()["data"]["access_token"])
        await asyncio.sleep(0.2)
    raise AssertionError(r.text)


async def _make_user(admin_client, suffix: str, roles: list[str]):
    pw = "Dash@2026!xyz"
    username = f"dash_{suffix}"
    r = await admin_client.post("/api/v1/users", json={
        "username": username, "email": f"{username}@test.com", "password": pw,
        "full_name": f"仪表盘 {suffix}", "department": "QV", "role_codes": roles,
    })
    assert r.status_code == 201, r.text
    return username, pw


@pytest.mark.asyncio
async def test_summary_forbidden_without_any_read_permission(admin_client, http_client, unique_suffix):
    """只有下游角色（QV_ENGINEER，MDM 内无任何权限）：仪表盘 403、甘特 403、搜索为空"""
    username, pw = await _make_user(admin_client, unique_suffix, ["QV_ENGINEER"])
    c = await _login_as(http_client, username, pw)
    r = await c.get("/api/v1/dashboard/summary")
    assert r.status_code == 403, r.text
    r = await c.get("/api/v1/dashboard/gantt")
    assert r.status_code == 403, r.text
    r = await c.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["data"]["permissions"] == []


@pytest.mark.asyncio
async def test_summary_trimmed_to_readable_domains(admin_client, http_client, unique_suffix):
    """只有设备管理员（equipment + material 读）：只回这两个域，其余键不出现；甘特无 project:read → 403"""
    username, pw = await _make_user(admin_client, unique_suffix, ["CMC_EQUIPMENT_ADMIN"])
    c = await _login_as(http_client, username, pw)
    r = await c.get("/api/v1/dashboard/summary")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data["visible_domains"]) == {"equipment", "material"}
    assert set(data["totals"]) == {"equipment", "material"}
    assert set(data["trend_30d"]) == {"equipment", "material"}
    assert set(data["distributions"]) == {
        "equipment_by_category", "equipment_by_status", "material_by_type", "material_by_grade"
    }
    r = await c.get("/api/v1/dashboard/gantt")
    assert r.status_code == 403
