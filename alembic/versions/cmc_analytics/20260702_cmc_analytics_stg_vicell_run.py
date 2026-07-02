"""cmc_analytics：staging.stg_vicell_run —— Vi-CELL 测样 staging（2026-07-02）

把 cmc_rd.raw_rd_usp_vicell 里每次测样解析成规整字段（项目/批号/罐号/培养天数）
写入 staging.stg_vicell_run（每次测样一行），供与工艺曲线结合分析。

样品号拆解规则（由 ETL 落数时执行，随日期切换）：
  - legacy（<=2026-07-01）：sample_id = 项目-批号-[罐号]_D天数，项目取首段；
  - v2（>=2026-07-02）：sample_id 不含项目 = 批号-罐号_D天数，项目取自 cell_type。
  末段永远是 D<天数>，倒数第二段是罐号，罐号前一段是批号。

命名与 staging.stg_batch 对齐：project_code(保留前导零)/batch_number/bioreactor_code/
batch_key(=项目_批号_罐)/parse_status。batch_key 用于 join mart.dim_batch 拿权威批次维度。
时间戳统一 TIMESTAMPTZ(UTC)，与 cmc_rd 全库口径一致。

写入脚本（后续）：rd-vicell-etl 的 stage 步骤。此迁移只建结构，ETL 账号授权随写入步骤另迁移。

Revision ID: cmc_analytics_stg_vicell
Revises: cmc_analytics_stg_batch
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_stg_vicell"
down_revision = "cmc_analytics_stg_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE staging.stg_vicell_run (
            source_system    text        NOT NULL,   -- 'vicell'
            source_instance  text,                    -- 例 rd_ws01_usp_vicell_01
            run_id           bigint      NOT NULL,    -- cmc_rd.raw_rd_usp_vicell.run.id（可溯源）
            sample_id        text        NOT NULL,    -- 原始样品号，审计用

            batch_key        text,                    -- 项目_批号_罐，拼不出则 NULL（join mart.dim_batch）
            project_code     text,                    -- 项目编号，保留前导零（'0092' != '92'）
            project_source   text,                    -- 'sample_id' | 'cell_type'，项目编号来源
            batch_number     text,                    -- 批号，R/B 打头
            bioreactor_code  text,                    -- 罐号（从 sample_id 解析）
            culture_day      integer,                 -- 培养天数（D8 -> 8）
            cell_type        text,                    -- 原始 cell_type（v2 下 = 项目编号），审计
            sample_id_scheme text,                    -- 'legacy'(含项目) | 'v2'(不含项目)
            parse_status     text        NOT NULL,    -- ok / ok_project_from_cell_type / unparseable

            run_date         timestamptz,             -- 上机时间（与工艺曲线按时间对齐）
            log_date         timestamptz,

            viable_per_ml    numeric(12,4),           -- VCD 活细胞密度（×10^6/mL），最关键
            viability_pct    numeric(7,4),            -- 活率 %
            total_per_ml     numeric(12,4),
            total_cells      integer,
            viable_cells     integer,
            avg_diameter_um  numeric(8,4),
            avg_circularity  numeric(6,4),

            built_by_run_id  bigint,                  -- 关联 raw_rd_usp_vicell.etl_log.id
            built_at         timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (run_id)
        );

        COMMENT ON TABLE  staging.stg_vicell_run IS
            'Vi-CELL 测样 staging（每次测样一行）。由 rd-vicell-etl stage 步骤从 cmc_rd 解析写入。';
        COMMENT ON COLUMN staging.stg_vicell_run.batch_key IS
            '标准批次键 = project_code_batch_number_bioreactor_code，与 stg_batch 对齐；拼不出则 NULL。';
        COMMENT ON COLUMN staging.stg_vicell_run.project_code IS
            '项目编号，字符串保留前导零。legacy 取自 sample_id 首段，v2 取自 cell_type。';
        COMMENT ON COLUMN staging.stg_vicell_run.bioreactor_code IS
            '罐号，从 sample_id 倒数第二段解析；应与 stg_batch.bioreactor_code 一致方能 join。';
        COMMENT ON COLUMN staging.stg_vicell_run.parse_status IS
            'ok / ok_project_from_cell_type / unparseable';
        """
    )

    # 建议索引：按批次键、按天数聚合查询用
    op.execute("CREATE INDEX idx_stg_vicell_batch_key ON staging.stg_vicell_run (batch_key)")
    op.execute(
        "CREATE INDEX idx_stg_vicell_project_batch "
        "ON staging.stg_vicell_run (project_code, batch_number)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS staging.stg_vicell_run")
