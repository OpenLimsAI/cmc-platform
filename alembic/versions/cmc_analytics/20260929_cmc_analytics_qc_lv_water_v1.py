"""Add water-system sampling context for QC LabVantage staging.

Revision ID: cmc_analytics_qc_lv_water_v1
Revises: cmc_analytics_qc_lv_ph_v1
"""

from alembic import op

revision = "cmc_analytics_qc_lv_water_v1"
down_revision = "cmc_analytics_qc_lv_ph_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE staging.stg_lv_sample
          ADD COLUMN samplepointid text,
          ADD COLUMN locationid text,
          ADD COLUMN eventdt timestamptz;

        ALTER TABLE staging.stg_lv_test_result_wide
          ADD COLUMN samplepointid text,
          ADD COLUMN locationid text,
          ADD COLUMN sample_eventdt timestamptz,
          ADD COLUMN receiveddt timestamptz,
          ADD COLUMN sample_createdt timestamptz,
          ADD COLUMN trend_dt timestamptz,
          ADD COLUMN trend_dt_source text;

        CREATE INDEX ix_stg_lv_sample_subtype_event
          ON staging.stg_lv_sample (source_system, samplesubtypeid, eventdt);
        CREATE INDEX ix_stg_lv_trw_water_trend
          ON staging.stg_lv_test_result_wide
             (source_system, samplesubtypeid, paramlistid, trend_dt);
        CREATE INDEX ix_stg_lv_trw_samplepoint
          ON staging.stg_lv_test_result_wide (source_system, samplepointid);

        COMMENT ON COLUMN staging.stg_lv_sample.eventdt IS
          'LabVantage S_SAMPLE.EVENTDT；水系统样品中作为取样/事件时间来源';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.sample_eventdt IS
          'LabVantage S_SAMPLE.EVENTDT 原值';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.trend_dt IS
          '趋势时间：collectiondt, eventdt, receiveddt, sample createdt 依次回退';
        COMMENT ON COLUMN staging.stg_lv_test_result_wide.trend_dt_source IS
          'trend_dt 实际采用的源字段，供审计和数据质量检查';
        COMMENT ON TABLE staging.stg_lv_test_result_wide IS
          'QC 已验证最终结果宽表；按 selection_rule 保存产品及水系统逐方法规则版本';
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Water-system sampling context may be consumed downstream; review and backup before removal"
    )
