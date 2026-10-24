"""Add auditable result-selection fields for QC LabVantage pH rule v1.

Revision ID: cmc_analytics_qc_lv_ph_v1
Revises: cmc_analytics_qc_lv_staging
"""

from alembic import op

revision = "cmc_analytics_qc_lv_ph_v1"
down_revision = "cmc_analytics_qc_lv_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE staging.stg_lv_test_result_wide
          ADD COLUMN samplestatus text,
          ADD COLUMN productid text,
          ADD COLUMN product_code text,
          ADD COLUMN dataitem_reportflag text,
          ADD COLUMN u_statisticflag text,
          ADD COLUMN spec_reportflag text,
          ADD COLUMN selection_rule text NOT NULL,
          ADD COLUMN selection_reason text NOT NULL;

        COMMENT ON COLUMN staging.stg_lv_test_result_wide.product_code IS
          'LabVantage s_batch.u_productcode；产品家族码，不从 source_instance 或名称推断';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.dataitem_reportflag IS
          'SDIDATAITEM.REPORTFLAG 原值';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.u_statisticflag IS
          'PARAMLISTITEM.U_STATISTICFLAG 原值，按方法版本和参数配置键关联';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.spec_reportflag IS
          '同一结果完整业务键关联的 SDIDATAITEMSPEC.REPORTFLAG；任一 Y 则记 Y';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.selection_rule IS
          '命中最终结果的版本化规则 ID';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.selection_reason IS
          '本行命中的结构化证据组合';

        CREATE INDEX ix_stg_lv_trw_product_code
          ON staging.stg_lv_test_result_wide (product_code);
        CREATE INDEX ix_stg_lv_trw_selection_rule
          ON staging.stg_lv_test_result_wide (selection_rule);
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Result-selection columns may contain audited data; review consumers and backup before removal"
    )
