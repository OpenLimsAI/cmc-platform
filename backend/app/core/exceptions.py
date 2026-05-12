"""
业务异常定义 - 与 API-MDM-001 错误码体系对齐
"""
from typing import Any


class AppError(Exception):
    """业务错误基类"""

    code: int = 50001
    http_status: int = 500
    error_type: str = "internal_error"
    default_message: str = "服务器内部错误"

    def __init__(
        self,
        message: str | None = None,
        details: list[dict[str, Any]] | None = None,
        **kwargs,
    ):
        self.message = message or self.default_message
        self.details = details or []
        self.context = kwargs
        super().__init__(self.message)


# ============== 4xx 客户端错误 ==============
class ValidationError(AppError):
    code = 40001
    http_status = 400
    error_type = "validation_failed"
    default_message = "校验失败"


class BadRequestError(AppError):
    code = 40000
    http_status = 400
    error_type = "bad_request"
    default_message = "请求格式错误"


class InvalidCredentialsError(AppError):
    code = 40101
    http_status = 401
    error_type = "invalid_credentials"
    default_message = "用户名或密码错误"


class TokenExpiredError(AppError):
    code = 40102
    http_status = 401
    error_type = "token_expired"
    default_message = "登录已过期，请重新登录"


class TokenInvalidError(AppError):
    code = 40103
    http_status = 401
    error_type = "token_invalid"
    default_message = "登录凭证无效"


class TokenMissingError(AppError):
    code = 40104
    http_status = 401
    error_type = "token_missing"
    default_message = "未登录"


class OldPasswordWrongError(AppError):
    code = 40105
    http_status = 401
    error_type = "old_password_wrong"
    default_message = "旧密码错误"


class PermissionDeniedError(AppError):
    code = 40301
    http_status = 403
    error_type = "permission_denied"
    default_message = "权限不足"


class AccountDisabledError(AppError):
    code = 40302
    http_status = 403
    error_type = "account_disabled"
    default_message = "账户已禁用"


class NotFoundError(AppError):
    code = 40400
    http_status = 404
    error_type = "not_found"
    default_message = "资源不存在"


class SubstanceNotFoundError(NotFoundError):
    code = 40402
    error_type = "substance_not_found"
    default_message = "Substance 不存在"


class ProjectNotFoundError(NotFoundError):
    code = 40403
    error_type = "project_not_found"
    default_message = "项目不存在"


class AssetNotFoundError(NotFoundError):
    code = 40405
    error_type = "asset_not_found"
    default_message = "资产不存在"


class ConflictError(AppError):
    code = 40901
    http_status = 409
    error_type = "conflict"
    default_message = "资源冲突"


class DuplicateCodeError(ConflictError):
    code = 40902
    error_type = "duplicate_code"
    default_message = "业务编码已存在"


class VersionConflictError(ConflictError):
    code = 40904
    error_type = "version_conflict"
    default_message = "数据已被他人修改，请刷新后重试"


class AccountLockedError(AppError):
    code = 42301
    http_status = 423
    error_type = "account_locked"
    default_message = "账户已锁定"


class RateLimitError(AppError):
    code = 42901
    http_status = 429
    error_type = "rate_limit_exceeded"
    default_message = "请求过于频繁"


class StateInvalidError(AppError):
    code = 42201
    http_status = 422
    error_type = "state_invalid"
    default_message = "状态机不允许的状态变更"


class XrefNotFoundError(NotFoundError):
    code = 40404
    error_type = "xref_not_found"
    default_message = "标识符不存在"


class SignatureRequiredError(AppError):
    """请求体未提供 password，但当前动作要求电子签名"""
    code = 42202
    http_status = 422
    error_type = "signature_required"
    default_message = "此操作需要电子签名，请在请求中提供密码"


class SignatureInvalidError(AppError):
    """电子签名密码验证失败"""
    code = 40106
    http_status = 401
    error_type = "signature_invalid"
    default_message = "电子签名验证失败：密码错误"
