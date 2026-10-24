"""cmab_qv baseline — 验证部平台独立库：四个 schema + 两个角色 + 默认权限（2026-09-10）

白皮书 V0.4 决策 D8 / 待落地项 L14。验证记录是 GMP 合规记录，不是研发数据的二次分析，
所以像 cmab_mdm 一样单独成库，放在 gmp_pg 实例（GMP 级备份）。库名照 cmab_mdm 规矩用 cmab_ 前缀（服务全公司）。

schema 分工：
  validation  验证任务台账、设备验证档案、报告与审批状态（应用业务数据）
  mapping     温湿度分布验证：一次验证的结果、测点、逐时刻数据（工具箱「保存本次结果」写这里）
  audit       审计追踪 —— 只许追加（qv_app 只有 SELECT/INSERT），不许改删
  meta        运行台账 / 系统配置

角色（密码由运维 ALTER ROLE 设置，不进 git）：
  qv_app     验证部平台后端：业务 schema 读写，audit 只增
  qv_reader  只读（报表 / 审计账号）

本迁移只建"地基"，不建业务表；表随功能逐个加迁移。
新环境：createdb cmab_qv → ./dbmig cmab_qv upgrade head。
"""
from __future__ import annotations

from alembic import op

revision = "cmab_qv_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMAS = {
    "validation": "验证任务台账、设备验证档案、报告与审批状态（验证部平台业务数据）",
    "mapping": "温湿度分布验证：验证结果、测点、逐时刻读数（qv-validation-platform 工具箱保存结果）",
    "audit": "审计追踪（只追加：qv_app 仅 SELECT/INSERT）",
    "meta": "运行台账与系统配置",
}
_ROLES = ("qv_app", "qv_reader")


def upgrade() -> None:
    for role in _ROLES:
        op.execute(
            f"""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN
                CREATE ROLE {role} LOGIN;  -- 密码由运维 ALTER ROLE 设置，不进 git
              END IF;
            END $$;
            """
        )
    op.execute("GRANT CONNECT ON DATABASE cmab_qv TO qv_app, qv_reader")
    op.execute(
        "COMMENT ON DATABASE cmab_qv IS "
        "'验证部平台独立库（白皮书 D8，2026-09-10）。GxP 级受控应用数据；设备台账读 cmab_mdm.eqp，账号读 cmab_mdm.auth，本库不存密码不建设备表。'"
    )

    for schema, comment in _SCHEMAS.items():
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        op.execute(f"COMMENT ON SCHEMA {schema} IS '{comment}'")
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO qv_app, qv_reader")
        if schema == "audit":
            app_priv = "SELECT, INSERT"
        else:
            app_priv = "SELECT, INSERT, UPDATE, DELETE"
        # 以后由 postgres（迁移账号）建的表/序列，自动带上这些权限，不用每张表再 GRANT
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} GRANT {app_priv} ON TABLES TO qv_app")
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} GRANT USAGE, SELECT ON SEQUENCES TO qv_app")
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} GRANT SELECT ON TABLES TO qv_reader")


def downgrade() -> None:
    for schema in _SCHEMAS:
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} REVOKE ALL ON TABLES FROM qv_app, qv_reader")
        op.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM qv_app")
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    op.execute("REVOKE CONNECT ON DATABASE cmab_qv FROM qv_app, qv_reader")
    # 角色是实例级对象、可能被别的库引用，这里不删。
