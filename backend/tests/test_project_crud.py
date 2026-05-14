"""
Project CRUD 关键路径测试（M2.1）
"""
import pytest


@pytest.mark.asyncio
async def test_create_project_returns_code(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest project {unique_suffix}",
            "project_type": "cmc",
            "project_phase": "phase_2",
            "department": "CMC R&D",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    # §9.2 编码格式：PRJ-YYYY-XXXX
    assert body["data"]["project_code"].startswith("PRJ-")
    assert body["data"]["status"] == "proposed"  # §9.2 默认值
    assert body["data"]["version"] == 1
    assert body["data"]["project_type"] == "cmc"


@pytest.mark.asyncio
async def test_get_project_after_create(admin_client, unique_suffix):
    create_resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest get project {unique_suffix}",
            "project_type": "clinical",
            "project_phase": "phase_1",
            "objective": "Build clinical Ph1 dossier",
        },
    )
    code = create_resp.json()["data"]["project_code"]

    get_resp = await admin_client.get(f"/api/v1/projects/{code}")
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["project_code"] == code
    assert data["project_name"] == f"pytest get project {unique_suffix}"
    assert data["project_type"] == "clinical"
    assert data["project_phase"] == "phase_1"
    assert data["objective"] == "Build clinical Ph1 dossier"


@pytest.mark.asyncio
async def test_list_projects_filters_and_pagination(admin_client, unique_suffix):
    # 创建 3 个不同类型的 project
    types = ["cmc", "clinical", "preclinical"]
    for i, t in enumerate(types):
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest list {unique_suffix} {t} {i}",
                "project_type": t,
            },
        )

    # q 关键字
    resp = await admin_client.get("/api/v1/projects", params={"q": unique_suffix, "page_size": 50})
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert sum(1 for it in items if unique_suffix in it["project_name"]) == 3

    # project_type 过滤
    resp_cmc = await admin_client.get(
        "/api/v1/projects",
        params={"q": unique_suffix, "project_type": "cmc", "page_size": 50},
    )
    cmc_items = [it for it in resp_cmc.json()["data"] if unique_suffix in it["project_name"]]
    assert len(cmc_items) == 1
    assert cmc_items[0]["project_type"] == "cmc"


@pytest.mark.asyncio
async def test_update_project_increments_version_exactly_one(admin_client, unique_suffix):
    """防回归：触发器自增 version，service 层不再 +=1"""
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest version {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    resp = await admin_client.put(
        f"/api/v1/projects/{code}",
        json={
            "version": 1,
            "change_reason": "测试 version 自增",
            "department": "QA",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["version"] == 2
    assert resp.json()["data"]["department"] == "QA"


@pytest.mark.asyncio
async def test_optimistic_lock_conflict(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest lock {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    resp = await admin_client.put(
        f"/api/v1/projects/{code}",
        json={"version": 99, "department": "should-fail"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40904
    assert resp.json()["meta"]["error"]["type"] == "version_conflict"


@pytest.mark.asyncio
async def test_invalid_project_type_rejected(admin_client, unique_suffix):
    """check constraint 应拒绝非法 project_type"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest invalid {unique_suffix}",
            "project_type": "invented_bad_value",
        },
    )
    # Pydantic 在 schema 层先拦截 → V1.1 §4.1 validation_failed → 400
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest delete {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/projects/{code}",
        json={"change_reason": "pytest 软删除回归测试"},
    )
    assert del_resp.status_code == 204

    # 软删后 GET 应 404
    get_resp = await admin_client.get(f"/api/v1/projects/{code}")
    assert get_resp.status_code == 404

    # 列表过滤也不应出现
    list_resp = await admin_client.get("/api/v1/projects", params={"q": unique_suffix})
    items = list_resp.json()["data"]
    assert all(it["project_code"] != code for it in items)


@pytest.mark.asyncio
async def test_soft_delete_requires_reason(admin_client, unique_suffix):
    """与 substance DELETE 同步要求 change_reason"""
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest del reason {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    # 缺 body / reason 太短 → V1.1 §4.1 validation_failed → 400
    resp = await admin_client.delete(f"/api/v1/projects/{code}")
    assert resp.status_code == 400

    resp = await admin_client.delete(
        f"/api/v1/projects/{code}", json={"change_reason": "no"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_project_audit_log_entity_code(admin_client, unique_suffix):
    """v2 audit trigger：project 自身 entity_code = project_code"""
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest audit {unique_suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]

    logs_resp = await admin_client.get(
        f"/api/v1/projects/{code}/audit-logs",
        params={"page_size": 20},
    )
    assert logs_resp.status_code == 200
    items = logs_resp.json()["data"]
    create_logs = [it for it in items if it["action"] == "CREATE"]
    assert create_logs, "应至少有一条 CREATE 审计"
    assert all(it["entity_code"] == code for it in create_logs)


@pytest.mark.asyncio
async def test_list_filter_priority_and_brief_fields(admin_client, unique_suffix):
    """P9 / P10（DEV-MDM-001 V1.2 Batch F）：列表过滤暴露 priority / program_name /
    confidentiality 等字段，ProjectBrief 返回 program_name / confidentiality /
    parent_project_id / sponsor_id。
    """
    pname = f"pytest brief {unique_suffix}"
    create_resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": pname,
            "project_type": "cmc",
            "priority": "high",
            "program_name": f"PRG-{unique_suffix}",
            "confidentiality": "restricted",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    code = create_resp.json()["data"]["project_code"]

    # P9：列表过滤 priority=high 命中
    list_resp = await admin_client.get(
        "/api/v1/projects",
        params={"priority": "high", "q": unique_suffix},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    target = next((it for it in items if it["project_code"] == code), None)
    assert target is not None, "priority=high 过滤应包含刚创建的项目"
    # P10：Brief 包含新暴露字段
    assert target["program_name"] == f"PRG-{unique_suffix}"
    assert target["confidentiality"] == "restricted"
    assert "parent_project_id" in target
    assert "sponsor_id" in target

    # P9：confidentiality=public 过滤应排除该项目
    list_resp2 = await admin_client.get(
        "/api/v1/projects",
        params={"confidentiality": "public", "q": unique_suffix},
    )
    items2 = list_resp2.json()["data"]
    assert all(it["project_code"] != code for it in items2)


@pytest.mark.asyncio
async def test_readonly_cannot_create_project(readonly_client, unique_suffix):
    """READ_ONLY_USER 缺 project:create"""
    resp = await readonly_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest forbidden {unique_suffix}",
            "project_type": "cmc",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40301
