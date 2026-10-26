"""
审计上下文：跨 middleware / dependency / service 传递当前请求的操作者信息

机制：
  ContextVar 在请求生命周期内传递 user_id / username / request_id / ip_address，
  通过 set_audit_session_vars(db) 注入到 PostgreSQL session（GUC），
  供 audit.fn_audit_trigger() 在 INSERT/UPDATE/DELETE 时读取。

为什么用 ContextVar 而不是 Request 参数：避免每个 get_db 调用点都要传 request，
也避免污染业务签名；Starlette/FastAPI 内部也基于 contextvars，asyncio 友好。
"""
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 默认值代表"系统/未登录"上下文（如 login endpoint 本身、健康检查等）
audit_user_id: ContextVar[int | None] = ContextVar("audit_user_id", default=None)
audit_username: ContextVar[str] = ContextVar("audit_username", default="system")
audit_request_id: ContextVar[str | None] = ContextVar("audit_request_id", default=None)
audit_ip: ContextVar[str | None] = ContextVar("audit_ip", default=None)


async def set_audit_session_vars(db: AsyncSession) -> None:
    """把当前 ContextVar 中的审计信息以 SET LOCAL 形式注入到当前事务

    一条 SELECT set_config 完成 4 个变量，等价于 4 个 SET LOCAL 但只一次往返。
    is_local=true 保证仅在当前事务内生效，事务结束自动失效，连接归还池子不会污染。
    """
    await db.execute(
        text(
            """
            SELECT
                set_config('app.user_id',    :user_id,    true),
                set_config('app.username',   :username,   true),
                set_config('app.request_id', :request_id, true),
                set_config('app.ip_address', :ip,         true)
            """
        ),
        {
            "user_id": str(audit_user_id.get()) if audit_user_id.get() is not None else "",
            "username": audit_username.get() or "system",
            "request_id": audit_request_id.get() or "",
            "ip": audit_ip.get() or "",
        },
    )
