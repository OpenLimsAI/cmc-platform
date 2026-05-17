# 应用配置：使用 pydantic-settings 从 .env 文件读取环境变量
# 依次查找 .env / ../.env，兼容本地直接运行和 Docker 挂载两种场景
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    admin_database_url: str = ""
    admin_password: str = "change_me"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    app_schema: str = "app_fastapi"
    # 额外允许的 CORS 来源（逗号分隔）。localhost:3000 始终允许，用于本机开发。
    # 示例：DEV_EXTRA_ORIGINS=http://192.168.1.100:3000,http://10.0.0.5:3000
    dev_extra_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        base = ["http://localhost:3000"]
        extras = [o.strip() for o in self.dev_extra_origins.split(",") if o.strip()]
        return base + extras


settings = Settings()
