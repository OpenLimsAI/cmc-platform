"""
/api/v1/search 全局跨域搜索路由

权限：登录即可调；service 内按 substance:read / project:read 过滤可见类型
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.models import User
from app.domains.search.services import GlobalSearchService
from app.shared.permissions import get_current_user

router = APIRouter()


@router.get("", summary="全局搜索（substance + project + asset）")
async def global_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=128, description="搜索关键字"),
    types: str | None = Query(
        None,
        description='逗号分隔："substance,project,asset"，缺省三者都返回',
    ),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    type_list = [t.strip() for t in types.split(",")] if types else None
    service = GlobalSearchService(db)
    hits = await service.search(q, type_list, limit, current_user=user)
    return success(
        data=[h.model_dump(mode="json") for h in hits],
        request_id=getattr(request.state, "request_id", None),
    )
