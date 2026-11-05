"""
PRS 业务服务层

M2.1：CRUD
M2.2：状态机 + status_history + milestones / team 子资源
M2.3 起：ref.project_substance link/unlink
"""
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    DuplicateCodeError,
    NotFoundError,
    ProjectNotFoundError,
    SignatureRequiredError,
    StateInvalidError,
    VersionConflictError,
)
from app.domains.ars.models import Asset
from app.domains.audit.schemas import SignatureBlock, StateChangeResponse, StatusHistoryItem
from app.domains.audit.signature_service import ESignatureService
from app.domains.auth.models import User
from app.domains.prs.models import (
    Project,
    ProjectMilestone,
    ProjectRelationship,
    ProjectStatusHistory,
    ProjectTeam,
)
from app.domains.prs.schemas import (
    ProjectBrief,
    ProjectCreate,
    ProjectDetail,
    ProjectFilter,
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectRelationshipCreate,
    ProjectRelationshipItem,
    ProjectTeamMemberCreate,
    ProjectUpdate,
)
from app.domains.prs.schemas import (
    ProjectMilestone as ProjectMilestoneSchema,
)
from app.domains.prs.schemas import (
    ProjectTeamMember as ProjectTeamMemberSchema,
)

# 状态机：action → {当前状态: 下一状态}
# SMP-RD-NUM-001 V2.1 §11.3 status：proposed/initiated/active/on_hold/
#   completed/terminated/cancelled；cancel = 立项后未启动即取消（migration 0047）
STATE_MACHINE: dict[str, dict[str, str]] = {
    "approve":   {"proposed": "initiated"},
    "start":     {"initiated": "active"},
    "hold":      {"active": "on_hold"},
    "resume":    {"on_hold": "active"},
    "complete":  {"active": "completed"},
    "terminate": {
        "proposed": "terminated",
        "initiated": "terminated",
        "active": "terminated",
        "on_hold": "terminated",
    },
    # SMP §11.3：cancelled 仅适用于尚未启动的项目（planned 语义），
    # 已启动/进行中项目走 terminate
    "cancel": {
        "proposed": "cancelled",
        "initiated": "cancelled",
    },
}

# GxP 关键动作要求电子签名；:start/:hold/:resume 是项目进度跟踪，非合规关键转移
SIGNATURE_REQUIRED_ACTIONS: set[str] = {"approve", "complete", "terminate", "cancel"}

ACTION_TO_MEANING: dict[str, str] = {
    "approve":   "approve",
    "start":     "review",
    "hold":      "review",
    "resume":    "review",
    "complete":  "approve",
    "terminate": "reject",
    "cancel":    "reject",
}


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- SMP §7.5 资产绑定校验 -----------
    async def _validate_asset_link(
        self, category: str | None, asset_id: int | None
    ) -> None:
        """asset_related 项目必须绑定一个存在的资产；non_asset 不得绑定。"""
        if category == "asset_related" and asset_id is None:
            raise BadRequestError(
                "project_category=asset_related 的项目必须指定 asset_id（SMP §7.5）"
            )
        if category == "non_asset" and asset_id is not None:
            raise BadRequestError(
                "project_category=non_asset 的项目不应绑定 asset_id（SMP §8）"
            )
        if asset_id is not None:
            result = await self.db.execute(
                select(Asset.asset_id).where(
                    Asset.asset_id == asset_id,
                    Asset.deleted_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is None:
                raise BadRequestError(f"asset_id={asset_id} 不存在或已删除")

    # ----------- SMP §7A 上市后变更条件校验 -----------
    @staticmethod
    def _validate_regulatory_change(
        nature: str | None, level: str | None, pre_approval: bool | None
    ) -> None:
        """nature=cmc_change/lcm 必填变更级别；major 级不得显式置 pre_approval=false。"""
        if nature in ("cmc_change", "lcm") and level is None:
            raise BadRequestError(
                "project_nature=cmc_change/lcm 的项目必须填写 regulatory_change_level（SMP §7A.4）"
            )
        if level == "major" and pre_approval is False:
            raise BadRequestError(
                "major 级变更 pre_approval_required 必须为 true（SMP §7A.4）"
            )

    # ----------- 编码生成（SMP V2.1 §7.1：CMAB-PRJ-YYYY-NNNN）-----------
    async def _next_project_code(self) -> str:
        # 用 meta.fn_ensure_year_sequence 拿当前年份序列名，再用 fn_next_code 取号
        # 前缀须与 prs.fn_project_assign_code 触发器一致（migration 0047）
        result = await self.db.execute(
            text(
                "SELECT meta.fn_next_code("
                "meta.fn_ensure_year_sequence('project', 'CMAB-PRJ-', "
                "EXTRACT(YEAR FROM NOW())::INT, 4))"
            )
        )
        code = result.scalar_one()
        if not isinstance(code, str):
            raise TypeError("Database code generator must return a string")
        return code

    # ----------- 列表 -----------
    async def list_projects(
        self,
        filter: ProjectFilter,
        page: int,
        page_size: int,
        sort: str | None = None,
    ) -> tuple[list[ProjectBrief], int]:
        stmt = select(Project).where(Project.deleted_at.is_(None))

        if filter.q:
            kw = f"%{filter.q}%"
            stmt = stmt.where(
                or_(
                    Project.project_code.ilike(kw),
                    Project.project_name.ilike(kw),
                    Project.project_name_en.ilike(kw),
                    Project.program_name.ilike(kw),
                    Project.objective.ilike(kw),
                )
            )
        if filter.project_type:
            types = [t.strip() for t in filter.project_type.split(",")]
            stmt = stmt.where(Project.project_type.in_(types))
        if filter.project_phase:
            phases = [p.strip() for p in filter.project_phase.split(",")]
            stmt = stmt.where(Project.project_phase.in_(phases))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Project.status.in_(statuses))
        if filter.project_category:
            cats = [c.strip() for c in filter.project_category.split(",")]
            stmt = stmt.where(Project.project_category.in_(cats))
        if filter.project_nature:
            natures = [n.strip() for n in filter.project_nature.split(",")]
            stmt = stmt.where(Project.project_nature.in_(natures))
        if filter.owning_function:
            funcs = [f.strip() for f in filter.owning_function.split(",")]
            stmt = stmt.where(Project.owning_function.in_(funcs))
        if filter.asset_id is not None:
            stmt = stmt.where(Project.asset_id == filter.asset_id)
        if filter.department:
            stmt = stmt.where(Project.department.ilike(f"%{filter.department}%"))
        if filter.project_manager_id is not None:
            stmt = stmt.where(Project.project_manager_id == filter.project_manager_id)
        if filter.priority:
            priorities = [p.strip() for p in filter.priority.split(",")]
            stmt = stmt.where(Project.priority.in_(priorities))
        if filter.program_name:
            stmt = stmt.where(Project.program_name.ilike(f"%{filter.program_name}%"))
        if filter.parent_project_id is not None:
            stmt = stmt.where(Project.parent_project_id == filter.parent_project_id)
        if filter.confidentiality:
            stmt = stmt.where(Project.confidentiality == filter.confidentiality)
        if filter.budget_currency:
            stmt = stmt.where(Project.budget_currency == filter.budget_currency)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                fname = f.lstrip("-+")
                col = getattr(Project, fname, None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Project.updated_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        projects = list(result.scalars().all())

        return [ProjectBrief.model_validate(p) for p in projects], total

    # ----------- 详情 -----------
    async def _get_project_or_404(self, code: str, for_update: bool = False) -> Project:
        # for_update：状态机等 check-then-act 路径加行锁，防并发覆写（H-12）
        stmt = select(Project).where(
            Project.project_code == code,
            Project.deleted_at.is_(None),
        )
        if for_update:
            stmt = stmt.with_for_update(of=Project).execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        proj = result.scalar_one_or_none()
        if not proj:
            raise ProjectNotFoundError(f"未找到 project: {code}")
        return proj

    async def get_by_code(self, code: str) -> ProjectDetail:
        proj = await self._get_project_or_404(code)
        return ProjectDetail.model_validate(proj)

    # ----------- 创建 -----------
    async def create(self, payload: ProjectCreate, current_user: User) -> ProjectDetail:
        # SMP §7.5：资产相关项目必须绑定存在的资产
        await self._validate_asset_link(payload.project_category, payload.asset_id)
        # SMP §7A：上市后变更条件校验
        self._validate_regulatory_change(
            payload.project_nature,
            payload.regulatory_change_level,
            payload.pre_approval_required,
        )
        # major 级默认需预先获批
        pre_approval = payload.pre_approval_required
        if payload.regulatory_change_level == "major" and pre_approval is None:
            pre_approval = True

        # project_code 由 BEFORE INSERT 触发器兜底；这里显式调一次以便立即拿到返回值
        code = await self._next_project_code()

        # 唯一性虽有 DB 约束，但提前命中可给更清晰错误
        exists = await self.db.execute(
            select(Project.project_id).where(Project.project_code == code)
        )
        if exists.scalar_one_or_none():
            raise DuplicateCodeError(f"project_code 冲突: {code}")

        proj = Project(
            project_code=code,
            project_name=payload.project_name,
            project_name_en=payload.project_name_en,
            project_type=payload.project_type,
            project_phase=payload.project_phase,
            project_category=payload.project_category,
            project_nature=payload.project_nature,
            owning_function=payload.owning_function,
            participating_functions=payload.participating_functions,
            asset_id=payload.asset_id,
            approval_reference=payload.approval_reference,
            governance_approval_ref=payload.governance_approval_ref,
            status_reason=payload.status_reason,
            sap_wbs_mapping=payload.sap_wbs_mapping,
            external_contract_refs=payload.external_contract_refs,
            partner_reference=payload.partner_reference,
            regulatory_change_level=payload.regulatory_change_level,
            pre_approval_required=pre_approval,
            comparability_study_ref=payload.comparability_study_ref,
            regulatory_submission_refs=payload.regulatory_submission_refs,
            legacy_project_id=payload.legacy_project_id,
            parent_project_id=payload.parent_project_id,
            program_name=payload.program_name,
            planned_start_date=payload.planned_start_date,
            planned_end_date=payload.planned_end_date,
            actual_start_date=payload.actual_start_date,
            actual_end_date=payload.actual_end_date,
            project_manager_id=payload.project_manager_id,
            sponsor_id=payload.sponsor_id,
            department=payload.department,
            budget_total=payload.budget_total,
            budget_currency=payload.budget_currency or "CNY",
            budget_actual=payload.budget_actual,
            objective=payload.objective,
            scope=payload.scope,
            deliverables=payload.deliverables,
            success_criteria=payload.success_criteria,
            priority=payload.priority,
            confidentiality=payload.confidentiality,
            description=payload.description,
            notes=payload.notes,
            extra=payload.extra,
            status="proposed",
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(proj)
        await self.db.flush()
        await self.db.refresh(proj)
        return ProjectDetail.model_validate(proj)

    # ----------- 更新 -----------
    async def update(
        self, code: str, payload: ProjectUpdate, current_user: User
    ) -> ProjectDetail:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )

        proj = await self._get_project_or_404(code, for_update=True)

        if proj.version != payload.version:
            raise VersionConflictError(
                f"版本号不匹配（服务器: {proj.version}，请求: {payload.version}）"
            )

        update_data = payload.model_dump(
            exclude_unset=True, exclude={"version", "change_reason"}
        )

        # SMP §7.5：按更新后的有效值校验资产绑定
        eff_category = update_data.get("project_category", proj.project_category)
        eff_asset_id = update_data.get("asset_id", proj.asset_id)
        if "project_category" in update_data or "asset_id" in update_data:
            await self._validate_asset_link(eff_category, eff_asset_id)

        # SMP §7A：按更新后的有效值校验上市后变更
        touches_reg = {"project_nature", "regulatory_change_level", "pre_approval_required"} & set(
            update_data
        )
        if touches_reg:
            eff_nature = update_data.get("project_nature", proj.project_nature)
            eff_level = update_data.get("regulatory_change_level", proj.regulatory_change_level)
            eff_pre = update_data.get("pre_approval_required", proj.pre_approval_required)
            self._validate_regulatory_change(eff_nature, eff_level, eff_pre)
            if eff_level == "major" and eff_pre is None:
                update_data["pre_approval_required"] = True

        for k, v in update_data.items():
            setattr(proj, k, v)
        proj.updated_by = current_user.user_id
        # version 与 updated_at 由 prs.fn_project_before_update 触发器维护

        await self.db.flush()
        await self.db.refresh(proj, ["version", "updated_at"])
        await self.db.commit()
        return ProjectDetail.model_validate(proj)

    # ----------- 软删除 -----------
    async def soft_delete(
        self, code: str, current_user: User, reason: str
    ) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        proj = await self._get_project_or_404(code)
        proj.deleted_at = datetime.now(UTC)
        proj.deleted_by = current_user.user_id
        # audit.fn_audit_trigger 检测 deleted_at NULL→NOT NULL，action 写为 'DELETE'
        await self.db.flush()

    # ----------- 状态机 -----------
    async def change_status(
        self,
        code: str,
        action: str,
        comment: str,
        current_user: User,
        signature: "SignatureBlock | None" = None,
    ) -> "StateChangeResponse":
        """状态机入口（API-MDM-001 V1.1 §7.4）"""
        from app.domains.audit.schemas import (  # 局部导入避免循环
            StateChangeResponse,
        )

        transitions = STATE_MACHINE.get(action)
        if not transitions:
            raise StateInvalidError(f"未知动作: {action}")

        requires_sig = action in SIGNATURE_REQUIRED_ACTIONS
        if requires_sig and signature is None:
            raise SignatureRequiredError(
                f"动作 '{action}' 为 GxP 关键转移，必须提供 signature 对象进行电子签名"
            )

        proj = await self._get_project_or_404(code, for_update=True)
        old_status = proj.status
        next_status = transitions.get(old_status)
        if not next_status:
            raise StateInvalidError(
                f"当前状态 '{old_status}' 不能执行 '{action}'"
                f"（允许的起始状态：{list(transitions)}）"
            )

        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": comment},
        )

        sig = None
        if signature is not None:
            sig_service = ESignatureService(self.db)
            sig = await sig_service.sign(
                user=current_user,
                password=signature.password,
                challenge_id=signature.challenge_id,
                entity_schema="prs",
                entity_table="project",
                entity_id=proj.project_id,
                entity_code=proj.project_code,
                meaning=signature.meaning or ACTION_TO_MEANING[action],
                reason=signature.reason,
                content_for_hash={
                    "project_code": proj.project_code,
                    "project_name": proj.project_name,
                    "current_status": old_status,
                    "target_status": next_status,
                    "version": proj.version,
                    "comment": comment,
                    "signature_reason": signature.reason,
                },
            )

        proj.status = next_status
        proj.updated_by = current_user.user_id
        proj.status_reason = comment
        today = date.today()
        # SMP §10.3：approve 回填立项批准日期与年份（approval_year 对齐编号年份）
        if action == "approve" and proj.approval_date is None:
            proj.approval_date = today
            proj.approval_year = today.year
        if action == "start" and proj.actual_start_date is None:
            proj.actual_start_date = today
        elif action == "complete" and proj.actual_end_date is None:
            proj.actual_end_date = today

        await self.db.flush()
        await self.db.execute(
            text(
                """
                UPDATE prs.project_status_history
                   SET change_reason  = :reason,
                       e_signature_id = :sid
                 WHERE history_id = (
                     SELECT MAX(history_id)
                       FROM prs.project_status_history
                      WHERE project_id = :proj_id
                 )
                """
            ),
            {
                "reason": comment,
                "sid": sig.signature_id if sig is not None else None,
                "proj_id": proj.project_id,
            },
        )
        await self.db.refresh(proj, ["version", "updated_at"])
        await self.db.commit()
        # PRS approve 把 proposed → initiated（不是 registered），但仍是注册流程的一部分；
        # registered_at/by 字段 PRS 表中不存在（V1.1 §9.2 没有），保持 None
        return StateChangeResponse(
            project_code=proj.project_code,
            old_status=old_status,
            new_status=proj.status,
            signature_id=sig.signature_id if sig is not None else None,
            version=proj.version,
        )

    # ----------- 状态历史 -----------
    async def get_status_history(self, code: str) -> list[StatusHistoryItem]:
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectStatusHistory)
            .where(ProjectStatusHistory.project_id == proj.project_id)
            .order_by(ProjectStatusHistory.changed_at.desc())
        )
        return [StatusHistoryItem.model_validate(h) for h in result.scalars()]

    # ----------- 里程碑（§9.3：无 deleted_at，硬删 + ON DELETE CASCADE 父项目）-----------
    async def list_milestones(self, code: str) -> list[ProjectMilestoneSchema]:
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id == proj.project_id)
            .order_by(
                ProjectMilestone.planned_date.asc(),
                ProjectMilestone.milestone_id.asc(),
            )
        )
        return [ProjectMilestoneSchema.model_validate(m) for m in result.scalars()]

    async def add_milestone(
        self, code: str, payload: ProjectMilestoneCreate, current_user: User
    ) -> ProjectMilestoneSchema:
        proj = await self._get_project_or_404(code)
        m = ProjectMilestone(
            project_id=proj.project_id,
            milestone_name=payload.milestone_name,
            milestone_type=payload.milestone_type,
            planned_date=payload.planned_date,
            actual_date=payload.actual_date,
            status=payload.status,
            description=payload.description,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(m)
        await self.db.flush()
        return ProjectMilestoneSchema.model_validate(m)

    async def update_milestone(
        self,
        code: str,
        milestone_id: int,
        payload: ProjectMilestoneUpdate,
        current_user: User,
    ) -> ProjectMilestoneSchema:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectMilestone).where(
                ProjectMilestone.milestone_id == milestone_id,
                ProjectMilestone.project_id == proj.project_id,
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            raise NotFoundError(f"milestone {milestone_id} 不属于 {code}")

        data = payload.model_dump(exclude_unset=True, exclude={"change_reason"})
        for k, v in data.items():
            setattr(m, k, v)
        m.updated_by = current_user.user_id
        await self.db.flush()
        return ProjectMilestoneSchema.model_validate(m)

    async def delete_milestone(
        self, code: str, milestone_id: int, current_user: User, reason: str
    ) -> None:
        """§9.3 物理删除（CASCADE 父项目场景由 DB 处理）"""
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectMilestone).where(
                ProjectMilestone.milestone_id == milestone_id,
                ProjectMilestone.project_id == proj.project_id,
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            raise NotFoundError(f"milestone {milestone_id} 不属于 {code}")
        await self.db.delete(m)
        await self.db.flush()

    # ----------- 团队 -----------
    async def list_team(self, code: str, include_left: bool = False) -> list[ProjectTeamMemberSchema]:
        proj = await self._get_project_or_404(code)
        stmt = select(ProjectTeam).where(ProjectTeam.project_id == proj.project_id)
        if not include_left:
            stmt = stmt.where(ProjectTeam.left_at.is_(None))
        stmt = stmt.order_by(ProjectTeam.joined_at.asc(), ProjectTeam.team_id.asc())
        result = await self.db.execute(stmt)
        return [ProjectTeamMemberSchema.model_validate(t) for t in result.scalars()]

    async def add_team_member(
        self, code: str, payload: ProjectTeamMemberCreate, current_user: User
    ) -> ProjectTeamMemberSchema:
        proj = await self._get_project_or_404(code)
        # auth.user 存在性校验
        u_result = await self.db.execute(
            select(User.user_id).where(
                User.user_id == payload.user_id,
                User.deleted_at.is_(None),
            )
        )
        if u_result.scalar_one_or_none() is None:
            raise BadRequestError(f"user_id={payload.user_id} 不存在或已停用")

        # 预检 (project, user, role) 在"未离职"范围内唯一
        # V1.2 评审 P3:A 决议（2026-05-13）：partial UNIQUE WHERE left_at IS NULL
        # 业务上允许离职后用同角色再加入
        existing = await self.db.execute(
            select(ProjectTeam.team_id).where(
                ProjectTeam.project_id == proj.project_id,
                ProjectTeam.user_id == payload.user_id,
                ProjectTeam.role == payload.role,
                ProjectTeam.left_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"该用户当前已是 {code} 的活跃 {payload.role}"
                f"（按 V1.2 §9.4 P3:A partial unique 决议：离职后可再加入）"
            )

        member = ProjectTeam(
            project_id=proj.project_id,
            user_id=payload.user_id,
            role=payload.role,
            function_area=payload.function_area,
            allocation_pct=payload.allocation_pct,
            notes=payload.notes,
            created_by=current_user.user_id,
        )
        self.db.add(member)
        await self.db.flush()
        return ProjectTeamMemberSchema.model_validate(member)

    async def remove_team_member(
        self,
        code: str,
        team_id: int,
        current_user: User,
        reason: str | None = None,
    ) -> None:
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectTeam).where(
                ProjectTeam.team_id == team_id,
                ProjectTeam.project_id == proj.project_id,
                ProjectTeam.left_at.is_(None),
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise NotFoundError(f"team_id={team_id} 不属于 {code} 或已离开")
        # §9.4 left_at 是 DATE 类型
        member.left_at = date.today()
        # current_user 已记录在 audit_log；§9.4 team 表本身无 updated_by 字段
        _ = current_user
        await self.db.flush()

    # ----------- 项目关系（SMP §11.4-11.6：合并/拆分/衍生）-----------
    async def list_relationships(self, code: str) -> list[ProjectRelationshipItem]:
        proj = await self._get_project_or_404(code)
        result = await self.db.execute(
            select(ProjectRelationship).where(
                or_(
                    ProjectRelationship.from_project_id == proj.project_id,
                    ProjectRelationship.to_project_id == proj.project_id,
                ),
                ProjectRelationship.deleted_at.is_(None),
            ).order_by(ProjectRelationship.relationship_id.asc())
        )
        rels = list(result.scalars().all())
        # 收集"对端"项目 id → (code, name)
        other_ids = {
            (r.to_project_id if r.from_project_id == proj.project_id else r.from_project_id)
            for r in rels
        }
        code_map: dict[int, tuple[str, str]] = {}
        if other_ids:
            rows = await self.db.execute(
                select(Project.project_id, Project.project_code, Project.project_name).where(
                    Project.project_id.in_(other_ids)
                )
            )
            code_map = {pid: (c, n) for pid, c, n in rows.all()}

        items: list[ProjectRelationshipItem] = []
        for r in rels:
            outgoing = r.from_project_id == proj.project_id
            other_id = r.to_project_id if outgoing else r.from_project_id
            other_code, other_name = code_map.get(other_id, (f"#{other_id}", ""))
            items.append(
                ProjectRelationshipItem.model_validate({
                    'relationship_id': r.relationship_id,
                    'relationship_type': r.relationship_type,
                    'direction': "outgoing" if outgoing else "incoming",
                    'other_project_code': other_code,
                    'other_project_name': other_name,
                    'notes': r.notes,
                    'created_at': r.created_at,
                })
            )
        return items

    async def add_relationship(
        self, code: str, payload: ProjectRelationshipCreate, current_user: User
    ) -> ProjectRelationshipItem:
        await self.db.execute(text("SELECT set_config('app.change_reason', :r, true)"), {"r": payload.change_reason})
        # 与项目状态操作采用一致的主表顺序；相同关系并发建立先重读，避免唯一性错误。
        await self.db.execute(select(Project).where(Project.project_code.in_([code, payload.to_project_code]))
            .order_by(Project.project_id).with_for_update().execution_options(populate_existing=True))
        from_proj = await self._get_project_or_404(code)
        to_proj = await self._get_project_or_404(payload.to_project_code)

        if from_proj.project_id == to_proj.project_id:
            raise BadRequestError("项目不能与自身建立关系")

        # 预检 (from, to, type) 唯一（DB 亦有 uq_project_relationship 兜底）
        existing = await self.db.execute(
            select(ProjectRelationship.relationship_id).where(
                ProjectRelationship.from_project_id == from_proj.project_id,
                ProjectRelationship.to_project_id == to_proj.project_id,
                ProjectRelationship.relationship_type == payload.relationship_type,
                ProjectRelationship.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"{code} → {payload.to_project_code} 的 {payload.relationship_type} 关系已存在"
            )

        rel = ProjectRelationship(
            from_project_id=from_proj.project_id,
            to_project_id=to_proj.project_id,
            relationship_type=payload.relationship_type,
            notes=payload.notes,
            created_by=current_user.user_id,
        )
        self.db.add(rel)
        await self.db.flush()
        await self.db.refresh(rel)
        item = ProjectRelationshipItem.model_validate({
                   'relationship_id': rel.relationship_id,
                   'relationship_type': rel.relationship_type,
                   'direction': "outgoing",
                   'other_project_code': to_proj.project_code,
                   'other_project_name': to_proj.project_name,
                   'notes': rel.notes,
                   'created_at': rel.created_at,
               })
        await self.db.commit()
        return item

    async def delete_relationship(
        self, code: str, relationship_id: int, current_user: User, reason: str | None = None
    ) -> None:
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        proj = await self._get_project_or_404(code)
        # 仅允许从属于该项目（任一端）的关系被删
        result = await self.db.execute(
            select(ProjectRelationship).where(
                ProjectRelationship.relationship_id == relationship_id,
                or_(
                    ProjectRelationship.from_project_id == proj.project_id,
                    ProjectRelationship.to_project_id == proj.project_id,
                ),
            ).with_for_update().execution_options(populate_existing=True)
        )
        rel = result.scalar_one_or_none()
        if not rel:
            raise NotFoundError(f"relationship_id={relationship_id} 不属于 {code}")
        if rel.deleted_at is not None:
            return
        rel.deleted_at = datetime.now(UTC)
        rel.deleted_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()
