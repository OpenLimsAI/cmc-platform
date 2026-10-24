# 应用配置：cmc_analytics 主库 + cmc_rd 旁路读
#   - analytics_database_url：lims_reader，cmc_analytics.mart.* 只读，dashboard 所有取数
#   - mdm_database_url：lims_mdm_writer，cmc_analytics.dim.{employee_master,method_master} 读写，admin 维护主数据（2026-09-10 前为 mdm.*）
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

    # ----------- 鉴权 / JWT 验签（令牌由 MDM 签发，本系统只验签，不发令牌）-----------
    # 与 MDM 对齐：HS256（dev，共享密钥）/ RS256（prod，MDM 公钥）。
    # 配了验签密钥 = 所有接口强制携带有效 JWT；没配 = 本地开放模式（方便开发）。
    auth_required: bool = False  # true 且未配验签密钥 → 启动即报错（防生产漏配裸奔）
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str = ""  # HS256：必须与 MDM 的 SECRET_KEY 完全相同
    jwt_public_key_path: str = ""  # RS256：MDM 公钥 PEM 文件路径
    mdm_base_url: str = ""  # 例 http://localhost:18000；留空则登录接口报 400
    cookie_secure: bool = False  # 内网 http 为 false，上 HTTPS 后置 true

    @model_validator(mode="after")
    def _forbid_unverifiable_auth(self) -> "Settings":
        # 非开发环境必须配置验签密钥，否则看板对所有人开放
        if self.app_env != "development" and not (self.jwt_secret_key or self.jwt_public_key_path):
            raise ValueError("生产环境必须配置 JWT_SECRET_KEY 或 JWT_PUBLIC_KEY_PATH（否则看板无鉴权裸奔）")
        return self


settings = Settings()
