"""cmc_analytics：mart.fact_nova 去重 dim_batch 关联（2026-08-11）

上线验证发现 dim_batch 有 23 个 batch_key 重复（同批号多条工艺记录，如中途重启），
LEFT JOIN 后 fact_nova 行数(8258)比 stg_nova_run(7921)多 337 行——一行取样被放大成
多行，画曲线会出重复点。这里改为先按 batch_key 去重再关联：优先取有 Lucullus
关联(procid 非空)、starttime 最新的一条。

注：fact_vicell 有同样的放大问题（16620→16701），另行处理。

Revision ID: cmc_analytics_fact_nova_dedup
Revises: cmc_analytics_fact_nova
Create Date: 2026-08-11

注：revision id 保持 ≤32 字符，否则超 alembic_version.version_num varchar(32) 会落库失败。
"""

from __future__ import annotations

from alembic import op

_VIEW_BODY = """
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
            -- 批次维度（batch_key 先去重再关联：优先有 Lucullus 关联、最新开始时间）
            b.experiment_purpose,
            b.line_code,
            b.batch_year,
            b.procid          AS lucullus_procid,
            b.starttime       AS batch_starttime,
            b.endtime         AS batch_endtime,
            b.duration_days   AS batch_duration_days,
            b.parse_status    AS batch_parse_status
        FROM staging.stg_nova_run v
        LEFT JOIN (
            SELECT DISTINCT ON (batch_key) *
            FROM mart.dim_batch
            WHERE batch_key IS NOT NULL
            ORDER BY batch_key, (procid IS NULL), starttime DESC NULLS LAST
        ) b ON b.batch_key = v.batch_key
"""

revision = "cmc_analytics_fact_nova_dedup"
down_revision = "cmc_analytics_fact_nova"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        f"""
        DROP VIEW mart.fact_nova;
        CREATE VIEW mart.fact_nova AS
        {_VIEW_BODY};

        COMMENT ON VIEW mart.fact_nova IS
            'Nova FLEX2 生化事实（每批次-罐-培养天一次取样一行）。stg_nova_run 左连去重后的 dim_batch，'
            '与 fact_vicell 同构，batch_key + culture_day 与细胞生长曲线对齐。';

        GRANT SELECT ON mart.fact_nova TO lims_reader, quality_user;
        """
    )


def downgrade() -> None:
    # 回退到未去重版本（cmc_analytics_fact_nova 的定义）
    op.execute(
        """
        DROP VIEW mart.fact_nova;
        CREATE VIEW mart.fact_nova AS
        SELECT
            v.sample_result_id, v.source_instance, v.analyzer_id, v.measured_at,
            v.sample_id, v.batch_key, v.project_id, v.batch_number, v.bioreactor_id,
            v.culture_day, v.gluc, v.lac, v.gln, v.glu, v.nh4, v.na, v.k, v.ca,
            v.ph, v.po2, v.pco2, v.parse_status, v.value_parse_status,
            v.experiment_purpose AS sample_experiment_purpose,
            b.experiment_purpose, b.line_code, b.batch_year,
            b.procid AS lucullus_procid, b.starttime AS batch_starttime,
            b.endtime AS batch_endtime, b.duration_days AS batch_duration_days,
            b.parse_status AS batch_parse_status
        FROM staging.stg_nova_run v
        LEFT JOIN mart.dim_batch b ON b.batch_key = v.batch_key;
        GRANT SELECT ON mart.fact_nova TO lims_reader, quality_user;
        """
    )
