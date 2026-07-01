from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 只读连接到 cmc_rd（走 SSH 隧道或 Linux 本机）。
    # 格式：postgresql+asyncpg://<只读账号>:<口令>@<host>:<port>/cmc_rd
    raw_database_url: str = ""

    app_env: str = "dev"
    # 前端开发地址，逗号分隔，用于 CORS（如 http://localhost:5140）
    dev_extra_origins: str = ""


settings = Settings()
