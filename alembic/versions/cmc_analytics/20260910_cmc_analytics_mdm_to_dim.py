"""cmc_analytics：mdm schema 并入 dim —— personnel → dim.employee_master，test_method → dim.method_master（2026-09-10）

白皮书 V0.4 决策 D10 / 待落地项 L11：`cmc_analytics.mdm` 与 MDM 门户（cmab_mdm）撞名，容易被当成登录账号表；
两张表本来就是白皮书 §3.1 规划的 dim.employee_master / dim.method_master，这次照规划归位。

做法：SET SCHEMA + RENAME（表、主键、CHECK、索引一并改名），数据一行不动；
依赖它们的视图 mart.dim_employee / mart.dim_method / mart.v_daily_workload 由 PG 按 OID 自动跟随，无需重建；
表上的权限（lims_admin 全权、lims_mdm_writer 读写、lims_reader / quality_user / lucullus_etl 只读）随表迁移，
只需补两个写角色对 dim schema 的 USAGE。最后删掉空的 mdm schema。

同步改代码：rd-lims-etl（每天 UPSERT 人员表）、cmc-rd-lims-dashboard（admin 面板 ORM）。

Revision ID: cmc_analytics_mdm_to_dim
Revises: cmc_analytics_manual_sample_time
Create Date: 2026-09-10
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_mdm_to_dim"
down_revision = "cmc_analytics_manual_sample_time"
branch_labels = None
depends_on = None

_MDM_USAGE = "lims_reader, quality_user, lims_admin, lucullus_etl, lims_mdm_writer"


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA dim TO lims_admin, lims_mdm_writer")

    # 人员
    op.execute("ALTER TABLE mdm.personnel SET SCHEMA dim")
    op.execute("ALTER TABLE dim.personnel RENAME TO employee_master")
    op.execute("ALTER TABLE dim.employee_master RENAME CONSTRAINT personnel_pkey TO employee_master_pkey")
    op.execute("ALTER TABLE dim.employee_master RENAME CONSTRAINT personnel_status_check TO employee_master_status_check")
    op.execute("ALTER INDEX dim.ix_personnel_group RENAME TO ix_employee_master_group")
    op.execute("ALTER INDEX dim.ix_personnel_status RENAME TO ix_employee_master_status")
    op.execute(
        "COMMENT ON TABLE dim.employee_master IS "
        "'检验/业务人员字典（原 mdm.personnel，2026-09-10 按白皮书 D10 归入 dim）。"
        "由 rd-lims-etl 每日从 LABLIMS.PERSONNEL 刷新，LIMS 看板 admin 面板可改。"
        "与 cmab_mdm.auth.user（登录账号）是两回事，只以工号 employee_id = auth.user.username 对齐。'"
    )

    # 方法
    op.execute("ALTER TABLE mdm.test_method SET SCHEMA dim")
    op.execute("ALTER TABLE dim.test_method RENAME TO method_master")
    op.execute("ALTER TABLE dim.method_master RENAME CONSTRAINT test_method_pkey TO method_master_pkey")
    op.execute("ALTER TABLE dim.method_master RENAME CONSTRAINT test_method_status_check TO method_master_status_check")
    op.execute("ALTER INDEX dim.ix_test_method_active RENAME TO ix_method_master_active")
    op.execute(
        "COMMENT ON TABLE dim.method_master IS "
        "'LIMS 检验方法字典（原 mdm.test_method，2026-09-10 按白皮书 D10 归入 dim）：标准工时 std_minutes、目标周转 target_days。"
        "由 LIMS 看板 admin 面板维护。'"
    )

    op.execute(
        "COMMENT ON VIEW mart.dim_employee IS "
        "'检测员维度（过滤软删）。读 dim.employee_master（2026-09-10 前为 mdm.personnel）。'"
    )
    op.execute(
        "COMMENT ON VIEW mart.dim_method IS "
        "'检验方法维度（过滤软删）。读 dim.method_master（2026-09-10 前为 mdm.test_method）。'"
    )

    op.execute("DROP SCHEMA mdm")  # 必须已空；有残留对象会报错，不会误删


def downgrade() -> None:
    op.execute("CREATE SCHEMA mdm")
    op.execute(f"GRANT USAGE ON SCHEMA mdm TO {_MDM_USAGE}")

    op.execute("ALTER INDEX dim.ix_method_master_active RENAME TO ix_test_method_active")
    op.execute("ALTER TABLE dim.method_master RENAME CONSTRAINT method_master_status_check TO test_method_status_check")
    op.execute("ALTER TABLE dim.method_master RENAME CONSTRAINT method_master_pkey TO test_method_pkey")
    op.execute("ALTER TABLE dim.method_master RENAME TO test_method")
    op.execute("ALTER TABLE dim.test_method SET SCHEMA mdm")

    op.execute("ALTER INDEX dim.ix_employee_master_status RENAME TO ix_personnel_status")
    op.execute("ALTER INDEX dim.ix_employee_master_group RENAME TO ix_personnel_group")
    op.execute("ALTER TABLE dim.employee_master RENAME CONSTRAINT employee_master_status_check TO personnel_status_check")
    op.execute("ALTER TABLE dim.employee_master RENAME CONSTRAINT employee_master_pkey TO personnel_pkey")
    op.execute("ALTER TABLE dim.employee_master RENAME TO personnel")
    op.execute("ALTER TABLE dim.personnel SET SCHEMA mdm")

    op.execute("REVOKE USAGE ON SCHEMA dim FROM lims_admin, lims_mdm_writer")
