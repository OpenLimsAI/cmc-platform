# 应用配置：cmc_analytics 主库 + cmc_rd 旁路读
#   - analytics_database_url：lims_reader，cmc_analytics.mart.* 只读，dashboard 所有取数
#   - mdm_database_url：lims_mdm_writer，cmc_analytics.mdm.* 读写，admin 维护主数据
#     如不设则回落到 analytics_database_url（但 lims_reader 无写权限，admin 写入会失败）
#   - raw_database_url：lims_reader，cmc_rd.meta.etl_run 只读，data-freshness 拿 ETL 跑完时间
#     留空时 data-freshness 不返回 etl_last_run_at（不致命）
from pydantic import model_validator
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
    log_level: str = "INFO"
    # 注：监听 host/port 固定在启动命令（uvicorn --port 8030 / docker-compose），
    # 不从这里读，所以本类不设 app_host/app_port 字段。
    # 额外允许的 CORS 来源（逗号分隔）。localhost:5130 始终允许,用于本机开发。
    # 本项目固定端口(编号 30,见 ~/code/PORTS.md):前端 5130 / 后端 8030。
    # 示例：DEV_EXTRA_ORIGINS=http://192.168.1.100:5130,http://10.0.0.5:5130
    dev_extra_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        base = ["http://localhost:5130"]
        extras = [o.strip() for o in self.dev_extra_origins.split(",") if o.strip()]
        return base + extras

    @model_validator(mode="after")
    def _forbid_default_password_in_prod(self) -> "Settings":
        # 非开发环境不允许沿用占位密码，避免生产忘配 ADMIN_PASSWORD 留空门
        if self.app_env != "development" and self.admin_password == "change_me":
            raise ValueError("生产环境必须设置 ADMIN_PASSWORD（当前仍是默认占位值）")
        return self


settings = Settings()
