"""只在保存阶段锁定主记录并核对开页版本。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, VersionConflictError
from app.domains.eqp.models import Equipment
from app.domains.mm.models import Material
from app.domains.target.models import Target


async def locked_master[RecordT: (Material, Equipment, Target)](db: AsyncSession, model: type[RecordT], code_field: str, code: str, version: int) -> RecordT:
    result = await db.execute(
        select(model).where(getattr(model, code_field) == code, model.deleted_at.is_(None))
        .with_for_update().execution_options(populate_existing=True)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError("该记录不存在或已删除，请刷新后重新检查")
    if record.version != version:
        raise VersionConflictError("该记录已被他人修改，本次保存未成功，请刷新后重新修改")
    return record
