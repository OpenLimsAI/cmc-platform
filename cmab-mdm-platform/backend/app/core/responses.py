"""
通用响应包装 - 与 API-MDM-001 通用响应格式对齐
"""
from datetime import UTC, datetime
from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def make(cls, page: int, page_size: int, total: int) -> "Pagination":
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if page_size else 0,
        )


class ResponseMeta(BaseModel):
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    api_version: str = "v1"
    pagination: Pagination | None = None


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorInfo(BaseModel):
    type: str
    details: list[ErrorDetail] = Field(default_factory=list)
    trace_id: str | None = None


class ErrorResponseMeta(ResponseMeta):
    error: ErrorInfo


class Response(BaseModel, Generic[T]):
    """统一成功响应"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: int = 0
    message: str = "OK"
    data: T | None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ListResponse(BaseModel, Generic[T]):
    """列表响应"""

    code: int = 0
    message: str = "OK"
    data: list[T] = Field(default_factory=list)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


def success(
    data: Any = None,
    message: str = "OK",
    request_id: str | None = None,
    pagination: Pagination | None = None,
) -> dict:
    """构造成功响应字典"""
    return {
        "code": 0,
        "message": message,
        "data": data,
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "api_version": "v1",
            "pagination": pagination.model_dump() if pagination else None,
        },
    }


def error_response(
    code: int,
    message: str,
    error_type: str = "error",
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict:
    """构造错误响应字典"""
    return {
        "code": code,
        "message": message,
        "data": None,
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "api_version": "v1",
            "error": {
                "type": error_type,
                "details": details or [],
            },
        },
    }
