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
    assert set(data.keys()) == {"totals", "distributions", "trend_30d"}
    assert set(data["totals"].keys()) == {"substance", "project", "asset", "material"}
    # 8 个分布
    assert set(data["distributions"].keys()) == {
        "substance_by_type",
        "substance_by_status",
        "project_by_status",
        "project_by_priority",
        "asset_by_phase",
        "asset_by_status",
        "material_by_type",
        "material_by_grade",
    }
    # 4 域趋势
    assert set(data["trend_30d"].keys()) == {"substance", "project", "asset", "material"}


@pytest.mark.asyncio
async def test_totals_match_list_endpoints(admin_client):
    """summary totals 必须与对应域 list 端点 pagination.total 一致"""
    r_sum = (await admin_client.get("/api/v1/dashboard/summary")).json()["data"]
    r_sub = (await admin_client.get("/api/v1/substances?page=1&page_size=1")).json()
    r_proj = (await admin_client.get("/api/v1/projects?page=1&page_size=1")).json()
    r_ast = (await admin_client.get("/api/v1/assets?page=1&page_size=1")).json()
    r_mat = (await admin_client.get("/api/v1/materials?page=1&page_size=1")).json()
    assert r_sum["totals"]["substance"] == r_sub["meta"]["pagination"]["total"]
    assert r_sum["totals"]["project"] == r_proj["meta"]["pagination"]["total"]
    assert r_sum["totals"]["asset"] == r_ast["meta"]["pagination"]["total"]
    assert r_sum["totals"]["material"] == r_mat["meta"]["pagination"]["total"]


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
    for entity in ("substance", "project", "asset", "material"):
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
