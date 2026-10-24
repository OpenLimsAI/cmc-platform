"""cmc_analytics：新建 dim schema + dim.equipment_master（设备维度权威表）（2026-07-24）

总纲把 `cmc_analytics.dim.equipment_master` 定为设备维度的**权威源**：
- 每个 `source_instance` 必须先在此注册；
- 下游要产线/厂商/型号等业务属性一律 **join 本表**，禁止字符串解析 `source_instance`。

但此前该表从未建出——vicell / lucullus 都只把 `source_instance` 当自由文本存，
没有权威维度可 join。本迁移补上这个地基。**这是新增表，不改动任何现有表，
不影响 vicell / lucullus 现有数据**（它们的 source_instance 仍是文本，将来可回填本表再 join）。

本次先注册 Nova FLEX2 一台；vicell / lucullus 的回填另行处理（非阻塞）。

Revision ID: cmc_analytics_dim_equipment
Revises: cmc_analytics_batch_startconf
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_dim_equipment"
down_revision = "cmc_analytics_batch_startconf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS dim")
    op.execute(
        "COMMENT ON SCHEMA dim IS "
        "'维度字典权威层（设备、厂商、单位、方法…）。下游 join 取业务属性，不解析标识符。'"
    )

    op.execute(
        """
        CREATE TABLE dim.equipment_master (
            source_instance   text PRIMARY KEY,   -- 唯一标识，格式 <env>_<line>_<stage>_<vendor>_<seq>
            analyzer_id       text,               -- 仪器机内 ID / 序列号（出现在导出文件名里）
            vendor            text NOT NULL,       -- 厂商可读全名，例 'Nova Biomedical'
            model             text,               -- 型号，例 'BioProfile FLEX2'
            instrument_type   text,               -- 仪器类别，例 'blood_gas_biochem' / 'cell_counter'

            -- 以下是 source_instance 各段的**解码值**，让下游直接取而非解析标识符（守铁律）
            env               text,               -- rd / gmp
            domain            text,               -- usp / dsp / dp / lims …
            line_code         text,               -- 产线/工位，例 'WS01'（对齐 mart.dim_batch.line_code）
            stage             text,               -- 工艺段，例 'usp'
            seq               text,               -- 同型号多机序号，例 '01'

            location          text,               -- 物理位置/实验室
            commissioned_on   date,               -- 首次投用日期（可考据自最早真实样品）
            status            text NOT NULL DEFAULT 'active',  -- active / retired / spare
            notes             text,

            registered_at     timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        );

        COMMENT ON TABLE dim.equipment_master IS
            '设备维度权威表。每个 source_instance 必须在此注册；下游取业务属性一律 join 本表，禁止解析 source_instance。';
        COMMENT ON COLUMN dim.equipment_master.source_instance IS
            '设备唯一标识 <env>_<line>_<stage>_<vendor>_<seq>。只作标识，其语义字段见本表其余列。';
        COMMENT ON COLUMN dim.equipment_master.line_code IS
            '产线/工位代码，与 mart.dim_batch.line_code 同口径，供按产线关联批次。';
        """
    )

    # 注册 Nova BioProfile FLEX2（本次接入的唯一一台）
    op.execute(
        """
        INSERT INTO dim.equipment_master
            (source_instance, analyzer_id, vendor, model, instrument_type,
             env, domain, line_code, stage, seq, location, commissioned_on, status, notes)
        VALUES
            ('rd_ws01_usp_nova_01', 'T281240040C', 'Nova Biomedical', 'BioProfile FLEX2',
             'blood_gas_biochem', 'rd', 'usp', 'WS01', 'usp', '01',
             'R&D 上游细胞培养实验室', '2025-05-20', 'active',
             '细胞培养生化/血气分析仪。数据经 cmc-instrument-ingest 归档、rd-nova-etl 入 raw_rd_usp_nova。首个真实样品 2025-05-20。')
        ON CONFLICT (source_instance) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE dim.equipment_master")
    # 只在 dim schema 为空时删（别误删将来别的迁移往 dim 里加的东西）
    op.execute("DROP SCHEMA IF EXISTS dim RESTRICT")
