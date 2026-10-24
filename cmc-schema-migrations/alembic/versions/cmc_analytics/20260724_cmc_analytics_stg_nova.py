"""cmc_analytics：staging.stg_nova_run —— Nova FLEX2 测样 staging（2026-07-24）

把 cmc_rd.raw_rd_usp_nova.sample_result 里每次测样解析成规整字段
（项目 / 批号 / 罐号 / 培养天数）写入 staging.stg_nova_run（每次测样一行），
供与工艺曲线、批次维度结合分析。由 rd-nova-etl 的 stage 步骤写入。

与 Vi-CELL 的关键差异（决定了拆解逻辑不同）：
  Vi-CELL 把项目/批号/罐号/天数全塞在一个 sample_id 里，靠位置拆；
  Nova 有**独立的列** batch_id / vessel_id / cell_type / sample_id，各管一段：
    - 项目 + 批号 → 主要来自 batch_id（'807-R2504' / '009-R2501-HCP' / 'R2606'）
    - 罐号        → 主要来自 vessel_id（'A6' / 'B3-B3' / 'SF12'），vessel_id 空时退到 batch_id 里被拼进去的段
    - 培养天数    → 来自 sample_id 的 '-DX' 后缀（'FBC-SN-D9' → 9）
    - 项目备选    → cell_type（'016' / '0092' 是项目编号；'CHO' 是真细胞类型）

命名与 staging.stg_vicell_run / stg_batch 对齐：
  project_id(保留前导零) / batch_number(R/B+4位) / bioreactor_id /
  batch_key(=项目_批号_罐) / parse_status。batch_key 用于 join mart.dim_batch。

Revision ID: cmc_analytics_stg_nova
Revises: cmc_analytics_dim_equipment
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_stg_nova"
down_revision = "cmc_analytics_dim_equipment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE staging.stg_nova_run (
            source_system     text        NOT NULL,   -- 'nova'
            source_instance   text,                    -- 例 rd_ws01_usp_nova_01（join dim.equipment_master）
            sample_result_id  bigint      NOT NULL,    -- cmc_rd.raw_rd_usp_nova.sample_result.id（可溯源）
            analyzer_id       text        NOT NULL,
            measured_at       timestamptz NOT NULL,    -- 测量时刻（与工艺曲线按时间对齐）

            -- 原始字段（审计用，保留操作员录入原样）
            sample_id         text,
            raw_batch_id      text,
            raw_vessel_id     text,
            raw_cell_type     text,

            -- 拆解结果（对齐 stg_batch / mart.dim_batch）
            batch_key         text,                    -- 项目_批号_罐，拼不出则 NULL
            project_id        text,                    -- 项目编号，保留前导零（'016' != '16'）
            project_source    text,                    -- 'batch_id' | 'cell_type'
            batch_number      text,                    -- 批号，R/B+4 位
            experiment_purpose text,                   -- 实验目的词（EOPC/HCP/MCB/WCB…），与 dim_batch 对齐
            bioreactor_id     text,                    -- 罐号
            bioreactor_source text,                    -- 'vessel_id' | 'batch_id'，罐号来源
            culture_day       integer,                 -- 培养天数（D9 → 9）
            parse_status      text        NOT NULL,    -- ok / suspect / unparseable / non_standard
            parse_note        text,

            -- 结果数值（趋势分析主力：生化通道齐全，血气约半数缺）
            gluc              numeric(12,4),           -- 葡萄糖
            lac               numeric(12,4),           -- 乳酸
            gln               numeric(12,4),
            glu               numeric(12,4),
            nh4               numeric(12,4),
            na                numeric(12,4),
            k                 numeric(12,4),
            ca                numeric(12,4),
            ph                numeric(8,4),
            po2               numeric(10,4),
            pco2              numeric(10,4),

            -- 数据质量沿袭 raw 层的解析溯源（下游过滤用）
            value_parse_status text,                   -- raw 的 parse_status：ok / shifted_repaired / shifted_unresolved

            built_at          timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (sample_result_id)
        );

        COMMENT ON TABLE  staging.stg_nova_run IS
            'Nova FLEX2 测样 staging（每次测样一行）。由 rd-nova-etl stage 步骤从 cmc_rd 解析写入，可全量重建。';
        COMMENT ON COLUMN staging.stg_nova_run.batch_key IS
            '标准批次键 = project_id_batch_number_bioreactor_id，与 stg_batch 对齐；拼不出则 NULL。';
        COMMENT ON COLUMN staging.stg_nova_run.project_id IS
            '项目编号，字符串保留前导零。取自 batch_id 前缀，缺则取 cell_type（若形如项目码）。';
        COMMENT ON COLUMN staging.stg_nova_run.bioreactor_source IS
            '罐号来源：vessel_id（独立列）或 batch_id（被拼进批号串里）。';
        COMMENT ON COLUMN staging.stg_nova_run.parse_status IS
            'ok(全解出) / suspect(解出但格式存疑) / unparseable(缺关键段) / non_standard(非标批号，非时程样)';
        COMMENT ON COLUMN staging.stg_nova_run.value_parse_status IS
            '沿袭 raw 层：shifted_unresolved 表示该行血气数值缺失（下游按需过滤）。';
        """
    )
    op.execute("CREATE INDEX idx_stg_nova_batch_key ON staging.stg_nova_run (batch_key)")
    op.execute(
        "CREATE INDEX idx_stg_nova_project_batch ON staging.stg_nova_run (project_id, batch_number)"
    )
    op.execute("CREATE INDEX idx_stg_nova_measured ON staging.stg_nova_run (measured_at)")


def downgrade() -> None:
    op.execute("DROP TABLE staging.stg_nova_run")
