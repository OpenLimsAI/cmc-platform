"""cmc_analytics：批次维度 staging.stg_batch + mart.dim_batch 视图（2026-07-02）

新增一步 PG→PG 转换的落地目标：把 cmc_rd 里 Lucullus 批次名解析成规整字段，
写入 cmc_analytics.staging.stg_batch（每单罐运行一行），并在其上建 mart.dim_batch
视图供看板消费。同时给 ETL 账号 lucullus_etl 补 staging.stg_batch 的写权限。

配套脚本：rd-lucullus-etl/lucullus_build_batch_dim.py（job=lucullus_build_batch_dim）。
时间戳列统一 TIMESTAMPTZ(UTC)，与 cmc_rd 全库口径一致。
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_stg_batch"
down_revision = "cmc_analytics_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS staging.stg_batch (
            source_system      text             NOT NULL,   -- 'lucullus'
            source_instance    text             NOT NULL,   -- 例 rd_ws01_usp_lucullus_01
            procid             bigint           NOT NULL,   -- Lucullus 内部批次号
            batch_key          text,                        -- 项目_批号_罐，拼不出则 NULL
            project_code       text,                        -- 保留前导零（'0092' != '92'）
            batch_number       text,                        -- 形如 R2501
            batch_year         integer,                     -- 2000 + 批号前两位
            batch_seq          integer,                     -- 批号后两位
            experiment_purpose text,                        -- EOPC / HCP 等，可空
            bioreactor_code    text,                        -- 权威罐号（来自 signal_timeseries.reactor_name）
            line_code          text,                        -- join equipment_lookup 得，缺登记则 NULL
            name_reactor       text,                        -- 批次名末段解析出的罐（仅校验用，已去重）
            reactor_match      boolean,                     -- name_reactor 是否与权威罐号一致
            parse_status       text             NOT NULL,   -- ok/ok_no_purpose/reactor_mismatch/suspect_test/unparseable
            procname_raw       text,                        -- 原始批次名，审计用
            starttime          timestamptz,                 -- 取自 process_src
            endtime            timestamptz,
            duration_days      double precision,            -- endtime-starttime 换算成天
            built_by_run_id    bigint,                      -- 关联 cmc_rd.meta.etl_run
            built_at           timestamptz      NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_instance, procid)
        );

        COMMENT ON TABLE  staging.stg_batch IS
            'Lucullus 批次维度（每单罐运行一行）。由 lucullus_build_batch_dim 从 cmc_rd 解析写入。';
        COMMENT ON COLUMN staging.stg_batch.batch_key IS
            '标准批次键 = project_code_batch_number_bioreactor_code（罐号取权威 reactor_name），拼不出则 NULL。';
        COMMENT ON COLUMN staging.stg_batch.project_code IS '项目编号，字符串保留前导零。';
        COMMENT ON COLUMN staging.stg_batch.bioreactor_code IS '权威罐号，来自 signal_timeseries.reactor_name。';
        COMMENT ON COLUMN staging.stg_batch.line_code IS
            '生产线编号，join cmc_rd.meta.equipment_lookup 得；设备未登记则 NULL（parse_status 无 line 单独在 etl 日志标记）。';
        COMMENT ON COLUMN staging.stg_batch.parse_status IS
            'ok / ok_no_purpose / reactor_mismatch / suspect_test / unparseable';
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW mart.dim_batch AS
        SELECT
            batch_key,
            project_code,
            batch_number,
            batch_year,
            experiment_purpose,
            bioreactor_code,
            line_code,
            source_instance,
            procid,
            procname_raw,
            starttime,
            endtime,
            duration_days,
            parse_status
        FROM staging.stg_batch;

        COMMENT ON VIEW mart.dim_batch IS
            '看板消费的批次维度（v1=stg_batch 视图）。将来多数据源汇入时改为物化表。';
        """
    )

    # ETL 账号 lucullus_etl 写 stg_batch（cmc_analytics 原则上只读，此表为 Lucullus ETL 例外写入点）
    op.execute(
        """
        GRANT CONNECT ON DATABASE cmc_analytics TO lucullus_etl;
        GRANT USAGE ON SCHEMA staging, mart TO lucullus_etl;
        GRANT SELECT, INSERT, UPDATE ON staging.stg_batch TO lucullus_etl;
        GRANT SELECT ON mart.dim_batch TO lucullus_etl;
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON mart.dim_batch FROM lucullus_etl;")
    op.execute("REVOKE ALL ON staging.stg_batch FROM lucullus_etl;")
    op.execute("DROP VIEW IF EXISTS mart.dim_batch;")
    op.execute("DROP TABLE IF EXISTS staging.stg_batch;")
