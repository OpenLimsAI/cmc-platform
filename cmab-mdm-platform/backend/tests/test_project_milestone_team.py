"""
Project milestones / team 子资源测试

M3.0.2 对齐 DM-MDM-001 V1.0 §9.3 / §9.4：
  - milestone_type ∈ {gate, deliverable, decision}
  - milestone status ∈ {planned, in_progress, completed, delayed, cancelled}
  - milestone.planned_date NOT NULL；硬删除（无 deleted_at）
  - team.role 任意字符串（无 CHECK），UNIQUE(project_id, user_id, role) 绝对唯一
  - team 新增 function_area / allocation_pct
  - team.joined_at / left_at: DATE
"""
import pytest


async def _create_project(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/projects",
            json={
                "project_name": f"pytest sub {suffix}",
                "project_type": "cmc",
            },
        )
    ).json()["data"]["project_code"]


# ============== Milestones ==============
@pytest.mark.asyncio
async def test_milestone_crud_roundtrip(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix)

    # 添加（planned_date NOT NULL；type 用 §9.3 三值之一）
    add = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={
            "milestone_name": "IND 申报",
            "milestone_type": "decision",
            "planned_date": "2026-09-30",
        },
    )
    assert add.status_code == 201, add.text
    mid = add.json()["data"]["milestone_id"]
    assert add.json()["data"]["status"] == "planned"  # §9.3 默认值

    # 列表
    lst = await admin_client.get(f"/api/v1/projects/{code}/milestones")
    assert lst.status_code == 200
    assert any(it["milestone_id"] == mid for it in lst.json()["data"])

    # 更新状态：planned → completed
    upd = await admin_client.put(
        f"/api/v1/projects/{code}/milestones/{mid}",
        json={
            "status": "completed",
            "actual_date": "2026-09-28",
            "change_reason": "pytest 标记完成",
        },
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["status"] == "completed"
    assert upd.json()["data"]["actual_date"] == "2026-09-28"

    # 硬删除（§9.3 无 deleted_at）
    deleted = await admin_client.delete(
        f"/api/v1/projects/{code}/milestones/{mid}",
        json={"change_reason": "pytest 删除里程碑"},
    )
    assert deleted.status_code == 204

    # 列表不再出现
    lst2 = await admin_client.get(f"/api/v1/projects/{code}/milestones")
    assert all(it["milestone_id"] != mid for it in lst2.json()["data"])


@pytest.mark.asyncio
async def test_milestone_invalid_type_rejected(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={
            "milestone_name": "X",
            "milestone_type": "bogus",
            "planned_date": "2026-12-31",
        },
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


@pytest.mark.asyncio
async def test_milestone_planned_date_required(admin_client, unique_suffix):
    """§9.3 planned_date NOT NULL"""
    code = await _create_project(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={"milestone_name": "X", "milestone_type": "gate"},
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


@pytest.mark.asyncio
async def test_milestone_type_required(admin_client, unique_suffix):
    """H-15：§9.3 milestone_type NOT NULL——缺省应 400 而非 500"""
    code = await _create_project(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={"milestone_name": "X", "planned_date": "2026-12-31"},
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


@pytest.mark.asyncio
async def test_milestone_type_update_explicit_null_rejected(admin_client, unique_suffix):
    """H-15：update 显式 milestone_type=null 应被 schema 拒绝，不得透传 DB"""
    code = await _create_project(admin_client, unique_suffix)
    add = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={
            "milestone_name": "M",
            "milestone_type": "gate",
            "planned_date": "2026-06-30",
        },
    )
    mid = add.json()["data"]["milestone_id"]
    resp = await admin_client.put(
        f"/api/v1/projects/{code}/milestones/{mid}",
        json={"milestone_type": None, "change_reason": "pytest 显式置空"},
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


@pytest.mark.asyncio
async def test_milestone_delete_requires_reason(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix)
    add = await admin_client.post(
        f"/api/v1/projects/{code}/milestones",
        json={
            "milestone_name": "M",
            "milestone_type": "gate",
            "planned_date": "2026-06-30",
        },
    )
    mid = add.json()["data"]["milestone_id"]
    # 缺 body
    resp = await admin_client.delete(
        f"/api/v1/projects/{code}/milestones/{mid}"
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


# ============== Team ==============
@pytest.mark.asyncio
async def test_team_add_and_remove(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix)

    # §9.4：role 任意字符串；新增 function_area / allocation_pct
    add = await admin_client.post(
        f"/api/v1/projects/{code}/team",
        json={
            "user_id": 2,
            "role": "CMC Lead",
            "function_area": "CMC",
            "allocation_pct": 80,
            "notes": "pytest 添加",
        },
    )
    assert add.status_code == 201, add.text
    tid = add.json()["data"]["team_id"]
    assert add.json()["data"]["left_at"] is None
    assert add.json()["data"]["role"] == "CMC Lead"
    assert add.json()["data"]["allocation_pct"] == 80

    # 列表
    lst = await admin_client.get(f"/api/v1/projects/{code}/team")
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    # 移除
    rm = await admin_client.delete(
        f"/api/v1/projects/{code}/team/{tid}",
        json={"change_reason": "pytest 移除成员"},
    )
    assert rm.status_code == 204

    # 默认列表不再出现
    lst2 = await admin_client.get(f"/api/v1/projects/{code}/team")
    assert len(lst2.json()["data"]) == 0

    # include_left=true 仍可见，left_at 是 DATE 字符串
    lst3 = await admin_client.get(
        f"/api/v1/projects/{code}/team", params={"include_left": "true"}
    )
    members = lst3.json()["data"]
    assert any(m["team_id"] == tid and m["left_at"] is not None for m in members)


@pytest.mark.asyncio
async def test_team_active_role_uniqueness(admin_client, unique_suffix):
    """V1.2 评审 P3:A 决议（migration 0031）：
    (project_id, user_id, role) partial UNIQUE WHERE left_at IS NULL —
    "已离职"行不参与去重，离职后可用同角色再加入。
    """
    code = await _create_project(admin_client, unique_suffix)
    payload = {"user_id": 2, "role": "PM"}

    # 1) 第一次加入：成功
    first = await admin_client.post(f"/api/v1/projects/{code}/team", json=payload)
    assert first.status_code == 201
    tid = first.json()["data"]["team_id"]

    # 2) 在活跃状态下重复加入：409（partial UNIQUE 在 left_at IS NULL 范围内）
    dup_active = await admin_client.post(f"/api/v1/projects/{code}/team", json=payload)
    assert dup_active.status_code == 409, "活跃成员重复加入应被拒"

    # 3) 移除（left_at 置为今天）
    await admin_client.delete(
        f"/api/v1/projects/{code}/team/{tid}",
        json={"change_reason": "pytest 离职"},
    )

    # 4) 再加同组合：P3:A 决议允许（已离职行不参与 partial UNIQUE）
    rejoin = await admin_client.post(f"/api/v1/projects/{code}/team", json=payload)
    assert rejoin.status_code == 201, "离职后用同角色再加入应被允许"
    assert rejoin.json()["data"]["team_id"] != tid, "应是新行而非重置原行"


@pytest.mark.asyncio
async def test_team_allocation_pct_bounds(admin_client, unique_suffix):
    """allocation_pct 0-100 范围校验（Pydantic + DB CHECK）"""
    code = await _create_project(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/projects/{code}/team",
        json={"user_id": 2, "role": "PM", "allocation_pct": 150},
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed


@pytest.mark.asyncio
async def test_team_add_nonexistent_user_rejected(admin_client, unique_suffix):
    code = await _create_project(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/projects/{code}/team",
        json={"user_id": 99999, "role": "Member"},
    )
    assert resp.status_code == 400
