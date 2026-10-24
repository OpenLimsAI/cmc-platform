"""cmc_rd: 新建 raw_rd_usp_nova schema（Nova BioProfile FLEX2 生化分析原始层）

Nova Biomedical BioProfile FLEX2 细胞培养生化分析仪的 raw 层，供 rd-nova-etl 写入。
3 张表：sample_result（测样主表）+ qc_result（质控）+ etl_log（运行日志）。
append-only，修正走 meta.data_correction_log。

命名遵循 raw_<env>_<domain>_<vendor>（usp=上游，vendor=nova）。
与 rd-nova-etl 仓库 sql/001_init_nova_schema.sql 对齐 —— **本迁移为权威源**。

几个和别的仪器不同、值得写在这里的设计：
- 自然键是 (analyzer_id, measured_at)：FLEX2 的导出没有样本级唯一 ID，
  测量时间戳是唯一可靠的键（实测 7710 条全不重复）。带上 analyzer_id 是为将来接第二台机器。
- parse_status / row_width / disabled_channels / value_source 这几列是**解析溯源**：
  该仪器的月度导出会在通道被禁用时省略整列（而非留空），导致后续列左移。
  这几列记录每条记录是"直接解析"还是"由重新导出文件补齐"，GMP 场景下要能说清数值来历。
- 试剂批号 4 列只有月度累积文件才有，是 GMP 可追溯链的关键。

Revision ID: cmc_rd_nova
Revises: cmc_rd_vicell_grant
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op

revision = "cmc_rd_nova"
down_revision = "cmc_rd_vicell_grant"
branch_labels = None
depends_on = None

_SCHEMA = "raw_rd_usp_nova"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA {_SCHEMA}")
    op.execute(
        f"COMMENT ON SCHEMA {_SCHEMA} IS "
        "'R&D 上游 Nova BioProfile FLEX2 生化分析仪原始数据。"
        "append-only，修正走 meta.data_correction_log。'"
    )

    op.execute(
        """
        CREATE TABLE raw_rd_usp_nova.etl_log (
        	id BIGSERIAL NOT NULL, 
        	run_started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	run_finished_at TIMESTAMP WITH TIME ZONE, 
        	status TEXT NOT NULL, 
        	files_scanned INTEGER NOT NULL, 
        	files_loaded INTEGER NOT NULL, 
        	files_skipped INTEGER NOT NULL, 
        	files_errored INTEGER NOT NULL, 
        	rows_inserted INTEGER NOT NULL, 
        	rows_skipped INTEGER NOT NULL, 
        	rows_conflict INTEGER NOT NULL, 
        	rows_unresolved INTEGER NOT NULL, 
        	error_details JSONB, 
        	watermark_before TIMESTAMP WITH TIME ZONE, 
        	watermark_after TIMESTAMP WITH TIME ZONE, 
        	PRIMARY KEY (id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE raw_rd_usp_nova.qc_result (
        	id BIGSERIAL NOT NULL, 
        	analyzer_id TEXT NOT NULL, 
        	source_instance TEXT, 
        	measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	qc_level TEXT, 
        	qc_lot_number TEXT, 
        	comment TEXT, 
        	operator TEXT, 
        	gln NUMERIC(14, 6), 
        	glu NUMERIC(14, 6), 
        	gluc NUMERIC(14, 6), 
        	lac NUMERIC(14, 6), 
        	nh4 NUMERIC(14, 6), 
        	na NUMERIC(14, 6), 
        	k NUMERIC(14, 6), 
        	ca NUMERIC(14, 6), 
        	ph NUMERIC(10, 6), 
        	po2 NUMERIC(14, 6), 
        	pco2 NUMERIC(14, 6), 
        	osm NUMERIC(14, 6), 
        	cell_density_flow NUMERIC(14, 6), 
        	total_density NUMERIC(14, 6), 
        	chemistry_flow_time NUMERIC(10, 4), 
        	ph_gas_flow_time NUMERIC(10, 4), 
        	source_file TEXT NOT NULL, 
        	file_sha256 TEXT, 
        	etl_loaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_qc_result_analyzer_measured_level UNIQUE (analyzer_id, measured_at, qc_level)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE raw_rd_usp_nova.sample_result (
        	id BIGSERIAL NOT NULL, 
        	analyzer_id TEXT NOT NULL, 
        	source_instance TEXT, 
        	measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	sample_time TIMESTAMP WITH TIME ZONE, 
        	sample_id TEXT, 
        	sample_type TEXT, 
        	comment TEXT, 
        	operator TEXT, 
        	gln NUMERIC(12, 4), 
        	glu NUMERIC(12, 4), 
        	gluc NUMERIC(12, 4), 
        	lac NUMERIC(12, 4), 
        	nh4 NUMERIC(12, 4), 
        	na NUMERIC(12, 4), 
        	k NUMERIC(12, 4), 
        	ca NUMERIC(12, 4), 
        	ph NUMERIC(8, 4), 
        	po2 NUMERIC(10, 4), 
        	pco2 NUMERIC(10, 4), 
        	ph_at_temp NUMERIC(8, 4), 
        	po2_at_temp NUMERIC(10, 4), 
        	pco2_at_temp NUMERIC(10, 4), 
        	o2_saturation NUMERIC(10, 4), 
        	co2_saturation NUMERIC(10, 4), 
        	hco3 NUMERIC(10, 4), 
        	pre_dilution_multiplier NUMERIC(10, 4), 
        	vessel_id TEXT, 
        	batch_id TEXT, 
        	cell_type TEXT, 
        	vessel_temperature_c NUMERIC(8, 3), 
        	vessel_pressure_psi NUMERIC(8, 3), 
        	sparging_o2_pct NUMERIC(8, 3), 
        	chemistry_flow_time NUMERIC(10, 4), 
        	ph_gas_flow_time NUMERIC(10, 4), 
        	chemistry_dilution_ratio TEXT, 
        	rsm TEXT, 
        	tray_location TEXT, 
        	time_in_tray TEXT, 
        	chemistry_cartridge_lot TEXT, 
        	chemistry_card_lot TEXT, 
        	gas_cartridge_lot TEXT, 
        	gas_card_lot TEXT, 
        	row_width SMALLINT, 
        	parse_status TEXT NOT NULL, 
        	value_source TEXT, 
        	disabled_channels JSONB, 
        	source_file TEXT NOT NULL, 
        	value_source_file TEXT, 
        	file_sha256 TEXT, 
        	etl_loaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_sample_result_analyzer_measured UNIQUE (analyzer_id, measured_at)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sample_result_batch_measured
            ON raw_rd_usp_nova.sample_result (batch_id, measured_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sample_result_measured
            ON raw_rd_usp_nova.sample_result (measured_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_sample_result_parse_status
            ON raw_rd_usp_nova.sample_result (parse_status) WHERE parse_status <> 'ok'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_qc_result_measured
            ON raw_rd_usp_nova.qc_result (measured_at)
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_rd_usp_nova.sample_result.parse_status IS
          'ok=等宽行按列名解析；shifted_repaired=短行，中段数值由重新导出文件补齐；shifted_unresolved=短行且补不到，中段为空（不可用于分析）'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_rd_usp_nova.sample_result.row_width IS
          '源文件里这一行的实际列数。<41 说明当时有通道被禁用、后续列整体左移'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_rd_usp_nova.sample_result.disabled_channels IS
          '该次测量被禁用的血气通道（血气校准不通过时操作员会关掉）。实测只有 pH/PO2/PCO2 出现过'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN raw_rd_usp_nova.sample_result.chemistry_cartridge_lot IS
          '试剂耗材批号，GMP 可追溯链。**只有月度累积文件有**，从行尾锚定取得'
        """
    )


def downgrade() -> None:
    op.execute(f"DROP SCHEMA {_SCHEMA} CASCADE")
