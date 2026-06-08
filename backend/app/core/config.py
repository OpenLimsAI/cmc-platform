"""
应用配置 - 从环境变量加载
"""
from functools import lru_cache

from pydantic import Field
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # ----------- 数据库 -----------
    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ----------- Redis -----------
    REDIS_URL: str = "redis://redis:6379/0"

    # ----------- 业务配置 -----------
    PASSWORD_MIN_LENGTH: int = 12
    # 管理员重置后临时密码有效期（用户必须在此期间登录并改密；超期 expires 拒登）
    PASSWORD_TEMP_DAYS: int = 7
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCK_DURATION_MINUTES: int = 30

    # ----------- 限流 -----------
    # 默认开启；测试 / 内网批量任务等可通过 env 关闭
    RATE_LIMIT_ENABLED: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
