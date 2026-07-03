from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 只读连接到 cmc_rd（原始层，Lucullus 工艺时序）。走 SSH 隧道或 Linux 本机。
    # 格式：postgresql+asyncpg://<只读账号>:<口令>@<host>:<port>/cmc_rd
    raw_database_url: str = ""

    # 只读连接到 cmc_analytics（分析层，Vi-CELL 细胞计数 mart.fact_vicell）。
    # 与 raw 同一实例、同一只读账号，只换库名 cmc_rd -> cmc_analytics。
    # 留空则「细胞生长曲线」接口不可用（工艺曲线不受影响）。
    analytics_database_url: str = ""

    app_env: str = "dev"
    # 前端开发地址，逗号分隔，用于 CORS（如 http://localhost:5170）
    dev_extra_origins: str = ""


settings = Settings()
