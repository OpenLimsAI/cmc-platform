"""
全局搜索 service

策略（M2.3 简单版）：
  - 对 srs.substance 和 prs.project 各跑一次 ILIKE 查询，附带 xref 命中
  - 排序按命中权重粗排：code 精确 > code 前缀 > 名称前缀 > 名称包含 > 其他
  - 跨域去重通过 (entity_type, code) 唯一
  - 权限：substance:read 才返回 substance；project:read 才返回 project；两者都没就空
  - 未引入 Elasticsearch；trgm GIN 索引已就位但此处用 ILIKE 简单查询，足够 M2.3
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ars.models import Asset
from app.domains.auth.models import User
from app.domains.prs.models import Project
from app.domains.search.schemas import SearchHit
from app.domains.srs.models import Substance, SubstanceXref
from app.shared.permissions import get_user_permissions


class GlobalSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        q: str,
        types: list[str] | None,
        limit: int,
        current_user: User,
    ) -> list[SearchHit]:
        q = q.strip()
        if not q:
            return []
        per_type_limit = max(limit, 20)
        is_sys_admin = any(r.role_code == "SYS_ADMIN" for r in current_user.roles)
        perms = await get_user_permissions(current_user, self.db)
        can_read_sub = is_sys_admin or "substance:read" in perms
        can_read_prj = is_sys_admin or "project:read" in perms
        can_read_ast = is_sys_admin or "asset:read" in perms
        wanted = set(types) if types else {"substance", "project", "asset"}

        hits: list[SearchHit] = []
        if "substance" in wanted and can_read_sub:
            hits.extend(await self._search_substance(q, per_type_limit))
        if "project" in wanted and can_read_prj:
            hits.extend(await self._search_project(q, per_type_limit))
        if "asset" in wanted and can_read_ast:
            hits.extend(await self._search_asset(q, per_type_limit))

        hits.sort(key=lambda h: _rank(h, q))
        return hits[:limit]

    async def _search_substance(self, q: str, lim: int) -> list[SearchHit]:
        pat = f"%{q}%"
        # 主表命中
        result = await self.db.execute(
            select(Substance)
            .where(
                Substance.deleted_at.is_(None),
                (Substance.substance_code.ilike(pat))
                | (Substance.preferred_name.ilike(pat))
                | (Substance.preferred_name_en.ilike(pat))
                | (Substance.internal_code.ilike(pat)),
            )
            .limit(lim)
        )
        items: dict[str, SearchHit] = {}
        for sub in result.scalars():
            field = _which_field_substance(q, sub)
            items[sub.substance_code] = SearchHit(
                entity_type="substance",
                code=sub.substance_code,
                name=sub.preferred_name,
                status=sub.status,
                matched_field=field,
                sub_type=sub.substance_type,
                snippet=sub.internal_code if field == "internal_code" else None,
            )

        # xref 命中（去重：已在主表命中的 substance 不再覆盖）
        xref_result = await self.db.execute(
            select(SubstanceXref, Substance)
            .join(Substance, Substance.substance_id == SubstanceXref.substance_id)
            .where(
                Substance.deleted_at.is_(None),
                SubstanceXref.deleted_at.is_(None),
                SubstanceXref.xref_value.ilike(pat),
            )
            .limit(lim)
        )
        for xref, sub in xref_result.all():
            if sub.substance_code not in items:
                items[sub.substance_code] = SearchHit(
                    entity_type="substance",
                    code=sub.substance_code,
                    name=sub.preferred_name,
                    status=sub.status,
                    matched_field="xref",
                    sub_type=sub.substance_type,
                    snippet=f"{xref.xref_type}: {xref.xref_value}",
                )
        return list(items.values())

    async def _search_project(self, q: str, lim: int) -> list[SearchHit]:
        pat = f"%{q}%"
        result = await self.db.execute(
            select(Project)
            .where(
                Project.deleted_at.is_(None),
                (Project.project_code.ilike(pat))
                | (Project.project_name.ilike(pat))
                | (Project.project_name_en.ilike(pat))
                | (Project.objective.ilike(pat))
                | (Project.program_name.ilike(pat)),
            )
            .limit(lim)
        )
        items = []
        for proj in result.scalars():
            field = _which_field_project(q, proj)
            items.append(
                SearchHit(
                    entity_type="project",
                    code=proj.project_code,
                    name=proj.project_name,
                    status=proj.status,
                    matched_field=field,
                    sub_type=proj.project_type,
                    snippet=proj.objective if field == "objective" else None,
                )
            )
        return items


    async def _search_asset(self, q: str, lim: int) -> list[SearchHit]:
        pat = f"%{q}%"
        result = await self.db.execute(
            select(Asset)
            .where(
                Asset.deleted_at.is_(None),
                (Asset.asset_code.ilike(pat))
                | (Asset.internal_name.ilike(pat))
                | (Asset.trade_name.ilike(pat))
                | (Asset.inn_name.ilike(pat))
                | (Asset.indication.ilike(pat)),
            )
            .limit(lim)
        )
        items = []
        for asset in result.scalars():
            field = _which_field_asset(q, asset)
            items.append(
                SearchHit(
                    entity_type="asset",
                    code=asset.asset_code,
                    name=asset.internal_name,
                    status=asset.status,
                    matched_field=field,
                    sub_type=asset.asset_type,
                    snippet=(
                        asset.trade_name if field == "trade_name"
                        else asset.inn_name if field == "inn_name"
                        else None
                    ),
                )
            )
        return items


def _which_field_substance(q: str, sub: Substance) -> str:
    ql = q.lower()
    if sub.substance_code and ql in sub.substance_code.lower():
        return "code"
    if sub.preferred_name and ql in sub.preferred_name.lower():
        return "name"
    if sub.preferred_name_en and ql in sub.preferred_name_en.lower():
        return "name_en"
    if sub.internal_code and ql in sub.internal_code.lower():
        return "internal_code"
    return "name"


def _which_field_project(q: str, proj: Project) -> str:
    ql = q.lower()
    if proj.project_code and ql in proj.project_code.lower():
        return "code"
    if proj.project_name and ql in proj.project_name.lower():
        return "name"
    if proj.project_name_en and ql in proj.project_name_en.lower():
        return "name_en"
    if proj.objective and ql in proj.objective.lower():
        return "objective"
    return "name"


def _which_field_asset(q: str, asset: Asset) -> str:
    ql = q.lower()
    if asset.asset_code and ql in asset.asset_code.lower():
        return "code"
    if asset.internal_name and ql in asset.internal_name.lower():
        return "name"
    if asset.trade_name and ql in asset.trade_name.lower():
        return "trade_name"
    if asset.inn_name and ql in asset.inn_name.lower():
        return "inn_name"
    return "name"


def _rank(hit: SearchHit, q: str) -> tuple[int, int]:
    """排序键：(权重, 名称长度) 双关键字升序。权重越小越靠前。"""
    ql = q.lower()
    cl = hit.code.lower()
    nl = hit.name.lower()
    if cl == ql:
        weight = 0
    elif cl.startswith(ql):
        weight = 1
    elif nl.startswith(ql):
        weight = 2
    elif hit.matched_field == "code":
        weight = 3
    elif hit.matched_field == "name":
        weight = 4
    elif hit.matched_field in ("name_en", "internal_code", "trade_name", "inn_name"):
        weight = 5
    elif hit.matched_field in ("xref", "objective"):
        weight = 6
    else:
        weight = 9
    return (weight, len(hit.name))
