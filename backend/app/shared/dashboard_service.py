"""
Phase 5.B 仪表盘聚合服务

跨 4 个业务域（SRS / PRS / ARS / MM）的统计聚合 + 项目甘特数据。
查询全部走 GROUP BY，单次往返；趋势按 30 天 created_at::date 聚合。

权限：登录即可（不暴露具体记录，只暴露聚合数据）。
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ars.models import Asset
from app.domains.eqp.models import Equipment
from app.domains.mm.models import Material
from app.domains.prs.models import Project, ProjectMilestone
from app.domains.srs.models import Substance
from app.domains.target.models import Target


async def _group_count(db: AsyncSession, table, col, *, where=None) -> list[dict]:
    stmt = select(col, func.count()).group_by(col)
    if where is not None:
        stmt = stmt.where(where)
    else:
        stmt = stmt.where(table.deleted_at.is_(None))
    result = await db.execute(stmt)
    return [{"key": k, "count": c} for k, c in result.all()]


async def _trend_30d(db: AsyncSession, table) -> list[dict]:
    """最近 30 天按 created_at::date 聚合新增数；空日填 0"""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=29)

    created_date = cast(table.created_at, DATE).label("d")
    result = await db.execute(
        select(created_date, func.count())
        .where(
            table.deleted_at.is_(None),
            table.created_at >= datetime(start.year, start.month, start.day, tzinfo=UTC),
        )
        .group_by(created_date)
        .order_by(created_date)
    )
    rows = {r[0]: r[1] for r in result.all()}

    series: list[dict] = []
    for i in range(30):
        d: date = start + timedelta(days=i)
        series.append({"date": d.isoformat(), "count": int(rows.get(d, 0))})
    return series


# 仪表盘按域裁剪（2026-09-10 负责人：无读权限的域不查不返；一个读权限都没有的账号不开放仪表盘）
DOMAINS = ("substance", "project", "asset", "material", "equipment", "target")
DOMAIN_READ_PERMISSION = {d: f"{d}:read" for d in DOMAINS}


def visible_domains_for(is_sys_admin: bool, permissions: set[str]) -> set[str]:
    if is_sys_admin:
        return set(DOMAINS)
    return {d for d, perm in DOMAIN_READ_PERMISSION.items() if perm in permissions}


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, domains: set[str] | None = None) -> dict:
        """domains：本次要统计的域（按调用方权限裁剪；None = 全部）。
        返回体只包含可见域的 totals / distributions / trend_30d，并带 visible_domains。"""
        visible = [d for d in DOMAINS if domains is None or d in domains]
        tables = {
            "substance": Substance, "project": Project, "asset": Asset,
            "material": Material, "equipment": Equipment, "target": Target,
        }
        dist_spec: dict[str, list[tuple[str, object]]] = {
            "substance": [("substance_by_type", Substance.substance_type), ("substance_by_status", Substance.status)],
            "project": [("project_by_status", Project.status), ("project_by_priority", Project.priority)],
            "asset": [("asset_by_phase", Asset.current_phase), ("asset_by_status", Asset.status)],
            "material": [("material_by_type", Material.material_type), ("material_by_grade", Material.grade)],
            "equipment": [("equipment_by_category", Equipment.category), ("equipment_by_status", Equipment.status)],
            "target": [("target_by_status", Target.status), ("target_by_entry_type", Target.entry_type)],
        }

        totals: dict[str, int] = {}
        distributions: dict[str, list[dict]] = {}
        trend_30d: dict[str, list[dict]] = {}
        for d in visible:
            table = tables[d]
            r = await self.db.execute(
                select(func.count()).select_from(table).where(table.deleted_at.is_(None))
            )
            totals[d] = int(r.scalar_one())
            for name, col in dist_spec[d]:
                distributions[name] = await _group_count(self.db, table, col)
            trend_30d[d] = await _trend_30d(self.db, table)

        return {
            "visible_domains": visible,
            "totals": totals,
            "distributions": distributions,
            "trend_30d": trend_30d,
        }

    async def get_gantt(self, project_status: str | None = None) -> list[dict]:
        """项目甘特数据：项目时间线 + 关键里程碑标记。

        - 只返回有 planned_start_date 或 actual_start_date 的项目（无时间线的提案不入图）
        - 终止项目（terminated）默认排除，可通过 project_status='terminated' 显式包含
        - milestone 取 milestone_name + planned_date + actual_date + status
        """
        stmt = select(Project).where(Project.deleted_at.is_(None))
        if project_status:
            stmt = stmt.where(Project.status == project_status)
        else:
            stmt = stmt.where(Project.status != "terminated")
        stmt = stmt.where(
            (Project.planned_start_date.isnot(None))
            | (Project.actual_start_date.isnot(None))
        )
        stmt = stmt.order_by(Project.planned_start_date.asc().nulls_last())

        result = await self.db.execute(stmt)
        projects = list(result.scalars())

        if not projects:
            return []

        # 批量拉里程碑
        pids = [p.project_id for p in projects]
        m_result = await self.db.execute(
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id.in_(pids))
            .order_by(ProjectMilestone.planned_date.asc())
        )
        milestones_by_project: dict[int, list[ProjectMilestone]] = {}
        for m in m_result.scalars():
            milestones_by_project.setdefault(m.project_id, []).append(m)

        items: list[dict] = []
        for p in projects:
            ms = milestones_by_project.get(p.project_id, [])
            items.append({
                "project_code": p.project_code,
                "project_name": p.project_name,
                "status": p.status,
                "priority": p.priority,
                "planned_start_date":
                    p.planned_start_date.isoformat() if p.planned_start_date else None,
                "planned_end_date":
                    p.planned_end_date.isoformat() if p.planned_end_date else None,
                "actual_start_date":
                    p.actual_start_date.isoformat() if p.actual_start_date else None,
                "actual_end_date":
                    p.actual_end_date.isoformat() if p.actual_end_date else None,
                "milestones": [
                    {
                        "milestone_id": m.milestone_id,
                        "milestone_name": m.milestone_name,
                        "planned_date":
                            m.planned_date.isoformat() if m.planned_date else None,
                        "actual_date":
                            m.actual_date.isoformat() if m.actual_date else None,
                        "status": m.status,
                    }
                    for m in ms
                ],
            })
        return items
