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

    # 人工录入（渗透压等）的写库连接：cmc_analytics 的写账号 usp_writer，只对 manual.sample_result 有追加权限。
    # 留空则「数据录入」页不可用（其余功能不受影响）。看板其它一切读操作仍走上面的只读连接。
    manual_write_database_url: str = ""
    # 批号注册系统（rd-batch-registry）后端地址，如 http://localhost:8080；数据录入页按日期取"当天该取样的样品清单"用。
    # 留空或不可达时退回只列仪器上实测到的样品。
    registry_base_url: str = ""

    app_env: str = "dev"
    # 前端开发地址，逗号分隔，用于 CORS（如 http://localhost:5170）
    dev_extra_origins: str = ""

    # ---- 统一认证（MDM Portal 代理登录 + 本地验签，规范见 ~/code/CLAUDE.md §8）----
    # 本项目不建用户表、不存密码、不签发令牌：登录转发 MDM，之后本地验签 MDM 的 JWT。
    mdm_base_url: str = ""  # MDM 后端地址，如 http://localhost:18000；留空则无法登录
    jwt_algorithm: str = "HS256"  # HS256（共享密钥）/ RS256（MDM 公钥文件）
    jwt_secret_key: str = ""  # HS256：必须与 MDM 的 SECRET_KEY 逐字符一致
    jwt_public_key_path: str = ""  # RS256：MDM 公钥 PEM 文件路径
    # 生产必须 true：要求鉴权但漏配验签密钥时启动即报错（防裸奔上线）。
    # false + 未配密钥 = 本地开放模式（不挡本地开发）。
    auth_required: bool = False
    # 允许查看本看板的角色码（逗号分隔）；SYS_ADMIN 是 MDM 规范的超管，始终该在列
    viewer_roles: str = "SYS_ADMIN,CMC_USP_RESEARCHER,CMC_USP_MANAGER,CMC_USP_OPERATOR"

    @property
    def viewer_role_set(self) -> set[str]:
        return {r.strip() for r in self.viewer_roles.split(",") if r.strip()}


settings = Settings()
