"""cmc_analytics：工艺按天聚合 + Vi-CELL×工艺合并（Phase 2，2026-07-03）

- staging.stg_process_daily：Lucullus 工艺参数按天聚合（长表，全通道日均/最值/末值），
  由 rd-lucullus-etl 的 lucullus_build_process_daily.py 从 cmc_rd.signal_timeseries 物化写入
  （无 FDW，走 PG→PG ETL，同 stg_batch）。
- mart.fact_process_daily：在长表上出宽表（核心通道 pH/DO/温度/搅拌/气体/加碱加酸 按天）。
- mart.fact_vicell_process：fact_vicell 左连 fact_process_daily（procid + 培养天），
  每 Vi-CELL 测样一行，VCD/活率旁边带当天工艺条件。这是"结合分析"的落点。

对齐假设：Vi-CELL 的 culture_day(如 D8→8) = floor(工艺 time_days)。差一天与否待真数据核对。

Revision ID: cmc_analytics_process_daily
Revises: cmc_analytics_vicell_grant
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_process_daily"
down_revision = "cmc_analytics_vicell_grant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 长表：每 (source_instance, procid, 培养天, 通道) 一行
    op.execute(
        """
        CREATE TABLE staging.stg_process_daily (
            source_system   text        NOT NULL,
            source_instance text        NOT NULL,
            procid          bigint      NOT NULL,
            bioreactor_id   text,
            batch_id        text,
            culture_day     integer     NOT NULL,
            channel_code    text        NOT NULL,
            channel_name    text,
            unitsymbol      text,
            value_mean      double precision,
            value_min       double precision,
            value_max       double precision,
            value_last      double precision,   -- 当天最后一个采样值（cumulative/setpoint 用）
            n_samples       integer,
            built_at        timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_instance, procid, culture_day, channel_code)
        );
        COMMENT ON TABLE staging.stg_process_daily IS
            'Lucullus 工艺参数按天聚合（长表，每 procid-培养天-通道一行）。'
            '由 lucullus_build_process_daily 从 cmc_rd.signal_timeseries 物化。';
        """
    )
    op.execute("GRANT USAGE ON SCHEMA staging TO lucullus_etl")
    op.execute("GRANT SELECT, INSERT, UPDATE ON staging.stg_process_daily TO lucullus_etl")

    # 2) 宽表视图：核心通道 pivot 成列，每 (procid, 培养天) 一行
    op.execute(
        """
        CREATE VIEW mart.fact_process_daily AS
        SELECT
            source_instance,
            procid,
            bioreactor_id,
            culture_day,
            max(value_mean) FILTER (WHERE channel_code='m_ph')      AS ph_mean,
            max(value_mean) FILTER (WHERE channel_code='m_temp')    AS temp_c_mean,
            max(value_mean) FILTER (WHERE channel_code='m_do')      AS do_pct_mean,
            min(value_min)  FILTER (WHERE channel_code='m_do')      AS do_pct_min,
            max(value_mean) FILTER (WHERE channel_code='m_stirrer') AS stirrer_rpm_mean,
            max(value_mean) FILTER (WHERE channel_code='m_o2')      AS o2_mlmin_mean,
            max(value_mean) FILTER (WHERE channel_code='m_air')     AS air_mlmin_mean,
            max(value_mean) FILTER (WHERE channel_code='m_co2')     AS co2_mlmin_mean,
            max(value_last) FILTER (WHERE channel_code='dm_alkali') AS alkali_cum_ml,
            max(value_last) FILTER (WHERE channel_code='dm_acid')   AS acid_cum_ml,
            max(n_samples)                                          AS n_samples_max
        FROM staging.stg_process_daily
        GROUP BY source_instance, procid, bioreactor_id, culture_day;

        COMMENT ON VIEW mart.fact_process_daily IS
            '工艺按天宽表（核心通道）。全通道见 staging.stg_process_daily。';
        """
    )

    # 3) 合并视图：Vi-CELL 测样 × 当天工艺
    op.execute(
        """
        CREATE VIEW mart.fact_vicell_process AS
        SELECT
            v.run_id, v.source_instance, v.sample_id, v.batch_key,
            v.project_id, v.batch_number, v.bioreactor_id, v.culture_day,
            v.run_date, v.log_date,
            v.viable_per_ml, v.viability_pct, v.total_per_ml,
            v.total_cells, v.viable_cells, v.avg_diameter_um, v.avg_circularity,
            v.experiment_purpose, v.line_code, v.lucullus_procid,
            v.parse_status,
            -- 当天工艺条件
            p.ph_mean, p.temp_c_mean, p.do_pct_mean, p.do_pct_min,
            p.stirrer_rpm_mean, p.o2_mlmin_mean, p.air_mlmin_mean, p.co2_mlmin_mean,
            p.alkali_cum_ml, p.acid_cum_ml
        FROM mart.fact_vicell v
        LEFT JOIN mart.fact_process_daily p
          ON p.procid = v.lucullus_procid AND p.culture_day = v.culture_day;

        COMMENT ON VIEW mart.fact_vicell_process IS
            'Vi-CELL 测样×当天工艺（每测样一行）。fact_vicell 左连 fact_process_daily(procid+培养天)。';
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.fact_vicell_process")
    op.execute("DROP VIEW IF EXISTS mart.fact_process_daily")
    op.execute("DROP TABLE IF EXISTS staging.stg_process_daily")
