"""
全局搜索 service

策略（M2.3 简单版）：
  - 对 srs.substance 和 prs.project 各跑一次 ILIKE 查询，附带 xref 命中
  - 排序按命中权重粗排：code 精确 > code 前缀 > 名称前缀 > 名称包含 > 其他
  - 跨域去重通过 (entity_type, code) 唯一
  - 权限：substance:read 才返回 substance；project:read 才返回 project；两者都没就空
  - 未引入 Elasticsearch；trgm GIN 索引已就位但此处用 ILIKE 简单查询，足够 M2.3
"""
from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ars.models import Asset
from app.domains.auth.models import User
from app.domains.eqp.models import Equipment
from app.domains.mm.models import Material
from app.domains.prs.models import Project
from app.domains.search.schemas import GlobalSearchResponse, SearchGroup, SearchHit
from app.domains.srs.models import Substance, SubstanceXref
from app.domains.target.models import Target
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
    ) -> GlobalSearchResponse:
        """API-MDM-001 V1.1 §8.3：响应按 entity_type 分组返回，
        含 query / total / results: {substance: {total, items}, project: {...}, asset: {...}}
        """
        q = q.strip()
        empty = GlobalSearchResponse(
            query=q,
            total=0,
            results={
                "substance": SearchGroup(total=0, items=[]),
                "project": SearchGroup(total=0, items=[]),
                "asset": SearchGroup(total=0, items=[]),
                "material": SearchGroup(total=0, items=[]),
                "equipment": SearchGroup(total=0, items=[]),
                "target": SearchGroup(total=0, items=[]),
            },
        )
        if not q:
            return empty

        per_type_limit = max(limit, 20)
        is_sys_admin = any(r.role_code == "SYS_ADMIN" for r in current_user.roles)
        perms = await get_user_permissions(current_user, self.db)
        can_read_sub = is_sys_admin or "substance:read" in perms
        can_read_prj = is_sys_admin or "project:read" in perms
        can_read_ast = is_sys_admin or "asset:read" in perms
        can_read_mat = is_sys_admin or "material:read" in perms
        can_read_eqp = is_sys_admin or "equipment:read" in perms
        can_read_tgt = is_sys_admin or "target:read" in perms
        wanted = (
            set(types)
            if types
            else {"substance", "project", "asset", "material", "equipment", "target"}
        )

        sub_hits: list[SearchHit] = []
        prj_hits: list[SearchHit] = []
        ast_hits: list[SearchHit] = []
        mat_hits: list[SearchHit] = []
        eqp_hits: list[SearchHit] = []
        tgt_hits: list[SearchHit] = []
        if "substance" in wanted and can_read_sub:
            sub_hits = await self._search_substance(q, per_type_limit)
        if "project" in wanted and can_read_prj:
            prj_hits = await self._search_project(q, per_type_limit)
        if "asset" in wanted and can_read_ast:
            ast_hits = await self._search_asset(q, per_type_limit)
        if "material" in wanted and can_read_mat:
            mat_hits = await self._search_material(q, per_type_limit)
        if "equipment" in wanted and can_read_eqp:
            eqp_hits = await self._search_equipment(q, per_type_limit)
        if "target" in wanted and can_read_tgt:
            tgt_hits = await self._search_target(q, per_type_limit)

        # 每组内部按权重排序 + 截断到 limit
        sub_hits.sort(key=lambda h: _rank(h, q))
        prj_hits.sort(key=lambda h: _rank(h, q))
        ast_hits.sort(key=lambda h: _rank(h, q))
        mat_hits.sort(key=lambda h: _rank(h, q))
        eqp_hits.sort(key=lambda h: _rank(h, q))
        tgt_hits.sort(key=lambda h: _rank(h, q))
        sub_hits = sub_hits[:limit]
        prj_hits = prj_hits[:limit]
        ast_hits = ast_hits[:limit]
        mat_hits = mat_hits[:limit]
        eqp_hits = eqp_hits[:limit]
        tgt_hits = tgt_hits[:limit]

        return GlobalSearchResponse(
            query=q,
            total=len(sub_hits) + len(prj_hits) + len(ast_hits) + len(mat_hits)
            + len(eqp_hits) + len(tgt_hits),
            results={
                "substance": SearchGroup(total=len(sub_hits), items=sub_hits),
                "project": SearchGroup(total=len(prj_hits), items=prj_hits),
                "asset": SearchGroup(total=len(ast_hits), items=ast_hits),
                "material": SearchGroup(total=len(mat_hits), items=mat_hits),
                "equipment": SearchGroup(total=len(eqp_hits), items=eqp_hits),
                "target": SearchGroup(total=len(tgt_hits), items=tgt_hits),
            },
        )

    async def _search_target(self, q: str, lim: int) -> list[SearchHit]:
        """靶点：编码 / 名称 / UniProt / 基因 / CD 号 / 别名（JSONB 转文本模糊匹配）"""
        pat = f"%{q}%"
        result = await self.db.execute(
            select(Target)
            .where(
                Target.deleted_at.is_(None),
                (Target.target_code.ilike(pat))
                | (Target.target_name.ilike(pat))
                | (Target.uniprot_id.ilike(pat))
                | (Target.gene_symbol.ilike(pat))
                | (cast(Target.cd_antigen_names, Text).ilike(pat))
                | (cast(Target.aliases, Text).ilike(pat))
                | (cast(Target.gene_synonyms, Text).ilike(pat)),
            )
            .limit(lim)
        )
        items = []
        for t in result.scalars():
            field, snippet = _which_field_target(q, t)
            mf = [k.get("name") for k in (t.keywords or []) if k.get("category") == "Molecular function"]
            items.append(
                SearchHit(
                    entity_type="target",
                    code=t.target_code,
                    name=t.target_name,
                    status=t.status,
                    matched_field=field,  # type: ignore[arg-type]
                    sub_type=(", ".join(mf[:2]) if mf else (t.cd_antigen_names or [None])[0]),
                    snippet=snippet,
                )
            )
        return items

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


    async def _search_material(self, q: str, lim: int) -> list[SearchHit]:
        pat = f"%{q}%"
        result = await self.db.execute(
            select(Material)
            .where(
                Material.deleted_at.is_(None),
                (Material.material_code.ilike(pat))
                | (Material.material_name.ilike(pat))
                | (Material.material_name_en.ilike(pat))
                | (Material.source_name.ilike(pat)),
            )
            .limit(lim)
        )
        items = []
        for mat in result.scalars():
            field = _which_field_material(q, mat)
            items.append(
                SearchHit(
                    entity_type="material",
                    code=mat.material_code,
                    name=mat.material_name,
                    status=mat.status,
                    matched_field=field,
                    sub_type=mat.material_type,
                    snippet=mat.source_name if field == "source_name" else None,
                )
            )
        return items


    async def _search_equipment(self, q: str, lim: int) -> list[SearchHit]:
        pat = f"%{q}%"
        result = await self.db.execute(
            select(Equipment)
            .where(
                Equipment.deleted_at.is_(None),
                (Equipment.equipment_code.ilike(pat))
                | (Equipment.equipment_no.ilike(pat))
                | (Equipment.fixed_asset_no.ilike(pat))
                | (Equipment.equipment_name.ilike(pat))
                | (Equipment.equipment_name_en.ilike(pat))
                | (Equipment.model.ilike(pat))
                | (Equipment.manufacturer.ilike(pat))
                | (Equipment.serial_no.ilike(pat)),
            )
            .limit(lim)
        )
        items = []
        for eq in result.scalars():
            field = _which_field_equipment(q, eq)
            items.append(
                SearchHit(
                    entity_type="equipment",
                    code=eq.equipment_code,
                    name=eq.equipment_name,
                    status=eq.status,
                    matched_field=field,
                    sub_type=eq.category,
                    snippet=(
                        eq.equipment_no if field == "equipment_no"
                        else eq.fixed_asset_no if field == "fixed_asset_no"
                        else eq.model if field == "model"
                        else eq.manufacturer if field == "manufacturer"
                        else eq.serial_no if field == "serial_no"
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


def _which_field_material(q: str, mat: Material) -> str:
    ql = q.lower()
    if mat.material_code and ql in mat.material_code.lower():
        return "code"
    if mat.material_name and ql in mat.material_name.lower():
        return "name"
    if mat.material_name_en and ql in mat.material_name_en.lower():
        return "name_en"
    if mat.source_name and ql in mat.source_name.lower():
        return "source_name"
    return "name"


def _which_field_equipment(q: str, eq) -> str:
    ql = q.lower()
    if eq.equipment_code and ql in eq.equipment_code.lower():
        return "code"
    if eq.equipment_no and ql in eq.equipment_no.lower():
        return "equipment_no"
    if eq.fixed_asset_no and ql in eq.fixed_asset_no.lower():
        return "fixed_asset_no"
    if eq.equipment_name and ql in eq.equipment_name.lower():
        return "name"
    if eq.equipment_name_en and ql in eq.equipment_name_en.lower():
        return "name_en"
    if eq.model and ql in eq.model.lower():
        return "model"
    if eq.manufacturer and ql in eq.manufacturer.lower():
        return "manufacturer"
    if eq.serial_no and ql in eq.serial_no.lower():
        return "serial_no"
    return "name"


def _which_field_target(q: str, t: Target) -> tuple[str, str | None]:
    ql = q.lower()
    if t.target_code and ql in t.target_code.lower():
        return "code", None
    if t.uniprot_id and ql in t.uniprot_id.lower():
        return "uniprot_id", t.uniprot_id
    if t.target_name and ql in t.target_name.lower():
        return "name", None
    if t.gene_symbol and ql in t.gene_symbol.lower():
        return "gene_symbol", t.gene_symbol
    for cd in t.cd_antigen_names or []:
        if ql in str(cd).lower():
            return "cd_antigen", cd
    for a in [*(t.aliases or []), *(t.gene_synonyms or [])]:
        if ql in str(a).lower():
            return "alias", a
    return "name", None


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
    elif hit.matched_field in (
        "name_en", "internal_code", "trade_name", "inn_name",
        "model", "manufacturer", "serial_no", "equipment_no", "fixed_asset_no",
    ):
        weight = 5
    elif hit.matched_field in ("xref", "objective", "source_name"):
        weight = 6
    else:
        weight = 9
    return (weight, len(hit.name))
