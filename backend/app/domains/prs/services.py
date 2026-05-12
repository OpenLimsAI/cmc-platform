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
from app.domains.audit.schemas import StatusHistoryItem
from app.domains.audit.signature_service import ESignatureService
from app.domains.auth.models import User
from app.domains.prs.models import (
    Project,
    ProjectMilestone,
    ProjectStatusHistory,
    ProjectTeam,
)
from app.domains.prs.schemas import (
    ProjectBrief,
    ProjectCreate,
    ProjectDetail,
    ProjectFilter,
    ProjectMilestone as ProjectMilestoneSchema,
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectTeamMember as ProjectTeamMemberSchema,
    ProjectTeamMemberCreate,
    ProjectUpdate,
)


# 状态机：action → {当前状态: 下一状态}
# 依据 DM-MDM-001 §9.2 status 枚举：proposed/initiated/active/on_hold/completed/terminated
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
}

# GxP 关键动作要求电子签名；:start/:hold/:resume 是项目进度跟踪，非合规关键转移
SIGNATURE_REQUIRED_ACTIONS: set[str] = {"approve", "complete", "terminate"}

ACTION_TO_MEANING: dict[str, str] = {
    "approve":   "approve",
    "start":     "review",
    "hold":      "review",
    "resume":    "review",
    "complete":  "approve",
    "terminate": "reject",
}


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 编码生成（§9.2：按年 PRJ-YYYY-XXXX）-----------
    async def _next_project_code(self) -> str:
        # 用 meta.fn_ensure_year_sequence 拿当前年份序列名，再用 fn_next_code 取号
        result = await self.db.execute(
            text(
                "SELECT meta.fn_next_code("
                "meta.fn_ensure_year_sequence('project', 'PRJ-', "
                "EXTRACT(YEAR FROM NOW())::INT, 4))"
            )
        )
        return result.scalar_one()

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
    async def _get_project_or_404(self, code: str) -> Project:
        result = await self.db.execute(
            select(Project).where(
                Project.project_code == code,
                Project.deleted_at.is_(None),
            )
        )
        proj = result.scalar_one_or_none()
        if not proj:
            raise ProjectNotFoundError(f"未找到 project: {code}")
        return proj

    async def get_by_code(self, code: str) -> ProjectDetail:
        proj = await self._get_project_or_404(code)
        return ProjectDetail.model_validate(proj)

    # ----------- 创建 -----------
    async def create(self, payload: ProjectCreate, current_user: User) -> ProjectDetail:
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

        proj = await self._get_project_or_404(code)

        if proj.version != payload.version:
            raise VersionConflictError(
                f"版本号不匹配（服务器: {proj.version}，请求: {payload.version}）"
            )

        update_data = payload.model_dump(
            exclude_unset=True, exclude={"version", "change_reason"}
        )
        for k, v in update_data.items():
            setattr(proj, k, v)
        proj.updated_by = current_user.user_id
        # version 与 updated_at 由 prs.fn_project_before_update 触发器维护

        await self.db.flush()
        await self.db.refresh(proj, ["version", "updated_at"])
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
        from app.domains.audit.schemas import SignatureBlock, StateChangeResponse  # 局部导入避免循环

        transitions = STATE_MACHINE.get(action)
        if not transitions:
            raise StateInvalidError(f"未知动作: {action}")

        requires_sig = action in SIGNATURE_REQUIRED_ACTIONS
        if requires_sig and signature is None:
            raise SignatureRequiredError(
                f"动作 '{action}' 为 GxP 关键转移，必须提供 signature 对象进行电子签名"
            )

        proj = await self._get_project_or_404(code)
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
        today = date.today()
        # M3.0.2：approved_at/by 字段已移除；审批时间从 status_history 推断
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

        # 预检 (project, user, role) 绝对唯一性（§9.4 普通 UNIQUE，无 partial WHERE 子句）
        existing = await self.db.execute(
            select(ProjectTeam.team_id).where(
                ProjectTeam.project_id == proj.project_id,
                ProjectTeam.user_id == payload.user_id,
                ProjectTeam.role == payload.role,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"该用户已是 {code} 的 {payload.role}（按 §9.4 唯一约束不可重复）"
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
