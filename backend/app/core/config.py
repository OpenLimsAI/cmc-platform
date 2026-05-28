# 应用配置：cmc_analytics 主库 + cmc_rd 旁路读
#   - analytics_database_url：lims_reader，cmc_analytics.mart.* 只读，dashboard 所有取数
#   - mdm_database_url：lims_mdm_writer，cmc_analytics.mdm.* 读写，admin 维护主数据
#     如不设则回落到 analytics_database_url（但 lims_reader 无写权限，admin 写入会失败）
#   - raw_database_url：lims_reader，cmc_rd.meta.etl_run 只读，data-freshness 拿 ETL 跑完时间
#     留空时 data-freshness 不返回 etl_last_run_at（不致命）
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    analytics_database_url: str
    mdm_database_url: str = ""
    raw_database_url: str = ""
    admin_password: str = "change_me"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    log_level: str = "INFO"
    # 额外允许的 CORS 来源（逗号分隔）。localhost:3000 始终允许，用于本机开发。
    # 示例：DEV_EXTRA_ORIGINS=http://192.168.1.100:3000,http://10.0.0.5:3000
    dev_extra_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        base = ["http://localhost:3000"]
        extras = [o.strip() for o in self.dev_extra_origins.split(",") if o.strip()]
        return base + extras


settings = Settings()
