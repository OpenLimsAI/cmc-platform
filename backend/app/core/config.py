# -*- coding: utf-8 -*-
"""应用配置（pydantic-settings，环境变量驱动）。

QAP 当前读取 cmc_analytics；Excel 功能仅内存预览，不配置业务写入连接。
这里配置数据库读取、CORS、MDM 验签/角色与端口。
默认值面向本机 Docker 测试环境（rd_pg:5432 / cmc_analytics）。生产应通过环境变量覆盖，
并使用中台分配的只读角色（如 lims_reader / quality_user，见白皮书 Part IV）。
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, StrictStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QAP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 服务 ----
    app_name: str = "QAP Backend"
    api_v1_prefix: str = "/api/v1"
    port: int = 8040  # 端口写死（PORTS.md 约定，编号 40）；前端 5140

    # ---- 数据库（只读消费 cmc_analytics）----
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "cmc_analytics"
    db_user: str = "postgres"          # 生产改为只读角色（lims_reader/quality_user）
    db_password: str = "postgres"
    db_schema: str = "staging"
    # Phase 1 数据来源标识：默认仅 R&D（白皮书：GMP 走 snap_gmp，QC 未就绪）
    source_systems: list[str] = Field(default_factory=lambda: ["rd_samplemanager"])

    # ---- 旧 API key 配置（兼容保留，不作为 MDM 身份或角色授权）----
    api_key: str = "dev-key"           # 已停用，不授予权限
    require_api_key: bool = False      # 已停用；认证由 MDM 配置控制

    # MDM 是唯一身份源。旧只读开发体验可匿名；Excel 预览始终验签及鉴权。
    environment: Literal["development", "test", "production"] = "development"
    auth_required: bool = False
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_secret_key: SecretStr | None = None
    jwt_public_key_path: str | None = None
    # 2026-09-16 负责人确认：QC综合可查看/导入，QA放行仅查看。
    # 当前只实现结构预览；正式确认导入能力仍关闭。配置可显式置空以关闭授权。
    read_roles: list[StrictStr] = Field(default_factory=lambda: ["QAP_QC_GENERAL", "QAP_QA_RELEASE"])
    import_preview_roles: list[StrictStr] = Field(default_factory=lambda: ["QAP_QC_GENERAL"])

    @field_validator("read_roles", "import_preview_roles")
    @classmethod
    def validate_role_names(cls, roles: list[str]) -> list[str]:
        if any(not role or role != role.strip() for role in roles):
            raise ValueError("角色白名单须为非空、不含首尾空格的角色码")
        return roles

    # ---- CORS ----
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5140", "http://127.0.0.1:5140"]
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_auth_settings() -> Settings:
    """独立的 FastAPI 依赖入口，测试可替换，不需要导入数据库。"""
    return get_settings()


settings = get_settings()
