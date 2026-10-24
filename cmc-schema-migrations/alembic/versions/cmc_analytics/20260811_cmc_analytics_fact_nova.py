"""cmc_analytics：mart.fact_nova —— Nova FLEX2 生化事实（2026-08-11）

照 mart.fact_vicell 的样子：staging.stg_nova_run 左连 mart.dim_batch（按 batch_key），
每 (批次-罐-培养天) 一次取样一行，供看板画生化趋势（葡萄糖/乳酸/氨/谷氨酰胺等）
并带批次上下文。视图形态（v1）。

注意：stg_nova_run 自带 experiment_purpose（从样本名解析），与 dim_batch 的同名列
区分——样本侧改名 sample_experiment_purpose，批次侧保持与 fact_vicell 一致。

Revision ID: cmc_analytics_fact_nova
Revises: cmc_analytics_batch_editlog_fk
Create Date: 2026-08-11

注：revision id 保持 ≤32 字符，否则超 alembic_version.version_num varchar(32) 会落库失败。
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_fact_nova"
down_revision = "cmc_analytics_batch_editlog_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW mart.fact_nova AS
        SELECT
            v.sample_result_id,
            v.source_instance,
            v.analyzer_id,
            v.measured_at,
            v.sample_id,
            v.batch_key,
            v.project_id,
            v.batch_number,
            v.bioreactor_id,
            v.culture_day,
            v.gluc,                   -- 葡萄糖 (g/L)
            v.lac,                    -- 乳酸 (g/L)
            v.gln,                    -- 谷氨酰胺 (mmol/L)
            v.glu,                    -- 谷氨酸 (mmol/L)
            v.nh4,                    -- 氨 (mmol/L)
            v.na,                     -- 钠 (mmol/L)
            v.k,                      -- 钾 (mmol/L)
            v.ca,                     -- 钙 (mmol/L)
            v.ph,
            v.po2,                    -- 氧分压 (mmHg)
            v.pco2,                   -- 二氧化碳分压 (mmHg)
            v.parse_status,
            v.value_parse_status,
            v.experiment_purpose AS sample_experiment_purpose,
            -- 批次维度（按 batch_key 关联 dim_batch，与 fact_vicell 同款）
            b.experiment_purpose,
            b.line_code,
            b.batch_year,
            b.procid          AS lucullus_procid,
            b.starttime       AS batch_starttime,
            b.endtime         AS batch_endtime,
            b.duration_days   AS batch_duration_days,
            b.parse_status    AS batch_parse_status
        FROM staging.stg_nova_run v
        LEFT JOIN mart.dim_batch b ON b.batch_key = v.batch_key;

        COMMENT ON VIEW mart.fact_nova IS
            'Nova FLEX2 生化事实（每批次-罐-培养天一次取样一行）。stg_nova_run 左连 dim_batch，'
            '与 fact_vicell 同构，batch_key + culture_day 与细胞生长曲线对齐。';
        """
    )
    # 显式给只读账号补 SELECT（默认权限一般已覆盖，这里幂等兜底）
    op.execute("GRANT SELECT ON mart.fact_nova TO lims_reader, quality_user")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.fact_nova")
