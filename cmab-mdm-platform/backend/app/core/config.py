"""
应用配置 - 从环境变量加载
"""
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ----------- 应用 -----------
    APP_NAME: str = "CMAB MDM Portal"
    # 产品版本（单一来源）：OpenAPI / /health / 根路由统一引用，避免多处硬编码漂移
    APP_VERSION: str = "V1.3-draft"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_LOG_LEVEL: str = "INFO"
    # 日志格式：human（开发彩色可读）/ json（生产单行 JSON 给 ELK/Splunk）
    APP_LOG_FORMAT: str = "human"
    APP_TIMEZONE: str = "Asia/Shanghai"

    # ----------- 安全 -----------
    # HS256 时 SECRET_KEY 必填；RS256 时仅作 fallback / 旧 token 兼容
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"  # 生产强烈建议 RS256（ARCH2）
    # RS256 启用时必填：PEM 格式 RSA 私钥/公钥的路径（容器内绝对路径）
    JWT_PRIVATE_KEY_PATH: str | None = None
    JWT_PUBLIC_KEY_PATH: str | None = None
    # JWT 头 kid 字段（启用 RS256 后用于密钥轮换；HS256 时忽略）
    JWT_KEY_ID: str | None = None
    # 2026-09-04 起会话时长改读 meta.system_config（session.* 键，系统管理页可调）；
    # 此项仅在库里缺行时兜底。REFRESH_TOKEN_EXPIRE_DAYS 已废弃（空闲窗口 + 硬上限替代）。
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # 2026-09-10 体检：以下三项原先都绑死在 APP_ENV/APP_DEBUG 上，导致「想开生产档就会连带
    # 打开/关闭别的东西」。拆开后 Linux 才能在 HTTP 内网下安全地跑 production：
    #   COOKIE_SECURE    refresh cookie 是否要求 HTTPS。绑死 is_production 时，一改 production
    #                    浏览器就丢弃 cookie → 全员无法续期。内网 HTTP 必须显式设 false。
    #   ENABLE_API_DOCS  /docs 与 openapi.json 是否对外开放（默认：生产关、开发开）
    #   RATE_LIMIT_*     限流阈值，可按实际情况调，不必改代码
    COOKIE_SECURE: bool | None = None
    ENABLE_API_DOCS: bool | None = None

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # ----------- 数据库 -----------
    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    # Separate approved PM identity; blank disables writes. Never reuse the MDM JWT.
    PM_PUBLIC_URL: str = ""
    PM_REFERENCE_API_URL: str = ""
    PM_REFERENCE_ACCESS_TOKEN: SecretStr | None = None
    # Opt-in MDM-only OIDC. Secrets stay server-side; native recovery remains explicit.
    MDM_OIDC_ENABLED: bool = False
    MDM_NATIVE_LOGIN_ENABLED: bool = True
    MDM_PUBLIC_URL: str = ""
    MDM_OIDC_ISSUER_URL: str = ""
    MDM_OIDC_INTERNAL_URL: str = ""
    MDM_OIDC_CLIENT_ID: str = ""
    MDM_OIDC_CLIENT_SECRET: SecretStr | None = None
    MDM_OIDC_PM_CLIENT_ID: str = ""
    MDM_OIDC_PM_CLIENT_SECRET: SecretStr | None = None
    MDM_OIDC_SESSION_MAX_SECONDS: int = Field(default=3600, ge=60, le=3600)
    MDM_PM_API_URL: str = ""
    MDM_PM_SOURCE_ID: str = "mdm"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ----------- Redis -----------
    REDIS_URL: str = "redis://redis:6379/0"

    # ----------- 业务配置 -----------
    PASSWORD_MIN_LENGTH: int = 8
    # 管理员重置后临时密码有效期（用户必须在此期间登录并改密；超期 expires 拒登）
    PASSWORD_TEMP_DAYS: int = 7
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCK_DURATION_MINUTES: int = 30

    # ----------- 限流 -----------
    # 默认开启；测试 / 内网批量任务等可通过 env 关闭
    RATE_LIMIT_ENABLED: bool = True
    # 阈值（留空则按环境取默认值，见下方 property）。格式如 "10/minute"
    RATE_LIMIT_LOGIN: str | None = None
    RATE_LIMIT_PUBLIC: str | None = None
    RATE_LIMIT_DEFAULT: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cookie_secure(self) -> bool:
        """refresh cookie 是否带 Secure 标记。显式配置优先；未配置时跟随环境。

        ⚠️ 内网 HTTP（http://172.19.0.105:5100）下必须为 false，否则浏览器直接丢弃该 cookie，
        用户登录后无法续期，到点全部掉线。上 HTTPS 后再改回 true。"""
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.is_production

    @property
    def enable_api_docs(self) -> bool:
        """是否开放 /docs 与 openapi.json。默认：生产关、开发开。"""
        if self.ENABLE_API_DOCS is not None:
            return self.ENABLE_API_DOCS
        return not self.is_production

    @property
    def rate_limit_login(self) -> str:
        # 生产 10/min/IP 防口令爆破；开发放宽，否则测试 fixture 每个用例登录会被打爆
        return self.RATE_LIMIT_LOGIN or ("10/minute" if self.is_production else "1000/minute")

    @property
    def rate_limit_public(self) -> str:
        # refresh 等公开端点：需带合法签名 cookie，不是爆破目标；但一个人可能同时开着
        # 门户 + 多个子系统，各自静默续期，10/min 会误伤，故放到 60/min
        return self.RATE_LIMIT_PUBLIC or ("60/minute" if self.is_production else "1000/minute")

    @property
    def rate_limit_default(self) -> str:
        return self.RATE_LIMIT_DEFAULT or ("300/minute" if self.is_production else "10000/minute")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
