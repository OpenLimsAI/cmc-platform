# -*- coding: utf-8 -*-
"""统一响应信封 {data, meta, errors} 与异常处理。

所有 API 响应遵循白皮书/SAD 约定：
    { "data": ..., "meta": {...}, "errors": [ {code, message, detail} ] }
"""
from typing import Any
import logging

from fastapi import FastAPI, Request, status
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def envelope(data: Any = None, meta: dict | None = None, errors: list | None = None) -> dict:
    return {"data": data, "meta": meta or {}, "errors": errors or []}


def error_item(code: str, message: str, detail: Any = None) -> dict:
    return {"code": code, "message": message, "detail": detail}


class BusinessError(Exception):
    """业务错误（如多时间单位、无数据），HTTP 200 但 errors 非空，前端据此提示。"""

    def __init__(self, code: str, message: str, detail: Any = None, http_status: int = 200):
        self.code = code
        self.message = message
        self.detail = detail
        self.http_status = http_status
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "请求被拒绝"
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=envelope(errors=[error_item(f"http_{exc.status_code}", message)]),
        )

    @app.exception_handler(BusinessError)
    async def _business(_req: Request, exc: BusinessError):
        return JSONResponse(
            status_code=exc.http_status,
            content=envelope(errors=[error_item(exc.code, exc.message, exc.detail)]),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope(
                errors=[error_item("validation_error", "请求参数校验失败", [
                    {"loc": list(error["loc"]), "type": error["type"]}
                    for error in exc.errors()
                ])]
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        # 不回显异常文本：底层连接/校验异常可能包含凭据或文件原值。
        logging.getLogger(__name__).error("Unhandled request exception type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope(errors=[error_item("internal_error", "服务暂时无法完成请求")]),
        )
