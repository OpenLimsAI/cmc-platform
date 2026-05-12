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
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_LOG_LEVEL: str = "INFO"
    APP_TIMEZONE: str = "Asia/Shanghai"

    # ----------- 安全 -----------
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
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
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCK_DURATION_MINUTES: int = 30

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
