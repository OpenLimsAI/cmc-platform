# 全局异常定义与处理
from fastapi import Request
from fastapi.responses import JSONResponse


class LIMSException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


async def lims_exception_handler(request: Request, exc: LIMSException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
