"""/api/v1/audit-logs 与 /api/v1/signatures 路由（Phase 5.A / M5.3）

权限：audit:read（SYS_ADMIN 自动通过）
端点：
- GET    /api/v1/audit-logs            — 全局审计日志查询
- POST   /api/v1/audit-logs:export     — 导出 CSV（响应 text/csv，max 50000 行）
- GET    /api/v1/signatures            — 电子签名列表

注：**不暴露 POST /signatures**（电子签名只能绑定到具体业务操作，与
21 CFR Part 11 §11.50/§11.70 上下文绑定要求一致）。
"""
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.audit.schemas import AuditLogFilter, SignatureFilter
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.shared.permissions import require_permission

audit_router = APIRouter()
signatures_router = APIRouter()


def _audit_filter(
    q: str | None = None,
    username: str | None = None,
    action: str | None = None,
    entity_table: str | None = None,
    entity_code: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogFilter:
    return AuditLogFilter(
        q=q,
        username=username,
        action=action,
        entity_table=entity_table,
        entity_code=entity_code,
        date_from=date_from,
        date_to=date_to,
    )


@audit_router.get("", summary="全局审计日志查询")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: AuditLogFilter = Depends(_audit_filter),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditService(db)
    items, total = await service.list_global_audit_logs(filter, page, page_size)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@audit_router.post(":export", summary="导出审计日志为 CSV（21 CFR Part 11 §11.10(c)）")
async def export_audit_logs(
    request: Request,
    filter: AuditLogFilter = Depends(_audit_filter),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    """同 GET 一样的筛选参数（query string），但响应 text/csv。

    单次最多导出 50000 行；超量请按 date_from/date_to 切片。
    """
    service = AuditService(db)
    csv_text, row_count = await service.export_audit_logs_csv(filter)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"audit_logs_{ts}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Row-Count": str(row_count),
        },
    )


def _signature_filter(
    username: str | None = None,
    entity_table: str | None = None,
    entity_code: str | None = None,
    signature_meaning: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SignatureFilter:
    return SignatureFilter(
        username=username,
        entity_table=entity_table,
        entity_code=entity_code,
        signature_meaning=signature_meaning,
        date_from=date_from,
        date_to=date_to,
    )


@signatures_router.get("", summary="电子签名列表（21 CFR Part 11 §11.50）")
async def list_signatures(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: SignatureFilter = Depends(_signature_filter),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditService(db)
    items, total = await service.list_signatures(filter, page, page_size)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )
