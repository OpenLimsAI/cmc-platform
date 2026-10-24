"""cmc_rd: 新建 raw_rd_usp_vicell schema（Vi-CELL XR 细胞计数原始层）

Beckman Coulter Vi-CELL XR 细胞活率/计数仪的 raw 层，供 rd-vicell-etl 写入。
7 张表：run（测样汇总主表）+ run_settings / run_image / run_size_distribution /
run_circ_distribution / run_cluster（明细）+ etl_log（运行日志）。
append-only，修正走 meta.data_correction_log。

命名遵循 raw_<env>_<domain>_<vendor>（usp=上游细胞检测，vendor=vicell）。
与 rd-vicell-etl 仓库 sql/001_init_vicell_schema.sql 对齐——本迁移为权威源。

Revision ID: cmc_rd_vicell
Revises: cmc_rd_timeunit_txt
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op

revision = "cmc_rd_vicell"
down_revision = "cmc_rd_timeunit_txt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA raw_rd_usp_vicell")
    op.execute(
        "COMMENT ON SCHEMA raw_rd_usp_vicell IS "
        "'R&D 上游 Vi-CELL XR 细胞计数仪原始数据。append-only，修正走 meta.data_correction_log。'"
    )

    # 1. run — 测样汇总主表
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run (
            id              BIGSERIAL PRIMARY KEY,
            sample_id       TEXT NOT NULL,
            file_name       TEXT NOT NULL,
            source_path     TEXT,
            source_instance TEXT,
            log_date        TIMESTAMPTZ,
            run_date        TIMESTAMPTZ,
            file_date       TIMESTAMPTZ,
            operator        TEXT,
            instrument_ver  TEXT,
            analysis_ver    TEXT,
            comment         TEXT,
            images          INTEGER NOT NULL,
            total_cells     INTEGER NOT NULL,
            viable_cells    INTEGER NOT NULL,
            nonviable_cells INTEGER NOT NULL,
            viability_pct   NUMERIC(7,4) NOT NULL,
            total_per_ml    NUMERIC(12,4) NOT NULL,
            viable_per_ml   NUMERIC(12,4) NOT NULL,
            avg_diameter_um NUMERIC(8,4) NOT NULL,
            avg_circularity NUMERIC(6,4) NOT NULL,
            avg_cells_per_image   NUMERIC(8,4),
            microns_per_pixel     NUMERIC(8,6),
            total_diameter_sum    NUMERIC(14,6),
            total_circularity_sum NUMERIC(12,6),
            bg_intensity_sum      INTEGER,
            file_checksum   TEXT,
            file_hash_etl   TEXT,
            etl_loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            etl_source_type TEXT NOT NULL DEFAULT 'txt',
            CONSTRAINT uq_run_sample_id_file_date UNIQUE (sample_id, file_date)
        )
        """
    )
    op.execute("CREATE INDEX idx_run_log_date ON raw_rd_usp_vicell.run (log_date)")
    op.execute("CREATE INDEX idx_run_sample_id ON raw_rd_usp_vicell.run (sample_id)")
    op.execute("COMMENT ON TABLE raw_rd_usp_vicell.run IS 'Vi-CELL 单次测样汇总（一文件一行）。'")
    op.execute(
        "COMMENT ON COLUMN raw_rd_usp_vicell.run.source_instance IS "
        "'设备唯一标识，如 rd_ws01_usp_vicell_01；业务属性 join dim.equipment_master，禁止字符串解析。'"
    )
    op.execute(
        "COMMENT ON COLUMN raw_rd_usp_vicell.run.file_checksum IS 'txt 内 CS 字段（仪器 SHA-1）。'"
    )
    op.execute(
        "COMMENT ON COLUMN raw_rd_usp_vicell.run.file_hash_etl IS 'ETL 自算文件 SHA-256，用于幂等去重。'"
    )

    # 2. run_settings — 仪器设置快照
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run_settings (
            id                  BIGSERIAL PRIMARY KEY,
            run_id              BIGINT NOT NULL REFERENCES raw_rd_usp_vicell.run(id) ON DELETE CASCADE,
            cell_type           TEXT,
            threshold_pct       INTEGER,
            center_threshold_pct INTEGER,
            min_diameter_um     NUMERIC(6,2),
            max_diameter_um     NUMERIC(6,2),
            min_center_size     NUMERIC(4,1),
            min_circularity     NUMERIC(4,2),
            frames              INTEGER,
            dilution_factor     NUMERIC(6,2),
            focus_parameter     INTEGER,
            flush_cycles        INTEGER,
            trypan_blue_cycles  INTEGER,
            internal_dilution   NUMERIC(6,3),
            decluster_degree    INTEGER,
            num_bins            INTEGER,
            fov_width_um        INTEGER,
            fov_height_um       INTEGER,
            sample_depth_um     NUMERIC(6,1),
            probe_volume_ul     NUMERIC(12,6),
            image_width_px      INTEGER,
            image_height_px     INTEGER,
            image_directory     TEXT,
            image_base_name     TEXT,
            CONSTRAINT uq_settings_run_id UNIQUE (run_id)
        )
        """
    )

    # 3. run_image — 逐帧数据（50帧/样本）
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run_image (
            id              BIGSERIAL PRIMARY KEY,
            run_id          BIGINT NOT NULL REFERENCES raw_rd_usp_vicell.run(id) ON DELETE CASCADE,
            image_index     SMALLINT NOT NULL,
            total_cells     INTEGER NOT NULL,
            viable_cells    INTEGER NOT NULL,
            viability_pct   NUMERIC(7,4),
            total_per_ml    NUMERIC(12,4),
            viable_per_ml   NUMERIC(12,4),
            avg_diameter_um NUMERIC(8,4),
            avg_circularity NUMERIC(6,4),
            bg_intensity    NUMERIC(8,2),
            CONSTRAINT uq_image_run_idx UNIQUE (run_id, image_index)
        )
        """
    )

    # 4. run_size_distribution — 粒径分布（140 bins/样本）
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run_size_distribution (
            id              BIGSERIAL PRIMARY KEY,
            run_id          BIGINT NOT NULL REFERENCES raw_rd_usp_vicell.run(id) ON DELETE CASCADE,
            bin_index       SMALLINT NOT NULL,
            bin_center_um   NUMERIC(8,4) NOT NULL,
            total_count     INTEGER NOT NULL,
            viable_count    INTEGER NOT NULL,
            CONSTRAINT uq_size_dist_run_bin UNIQUE (run_id, bin_index)
        )
        """
    )

    # 5. run_circ_distribution — 圆度分布（100 bins/样本）
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run_circ_distribution (
            id              BIGSERIAL PRIMARY KEY,
            run_id          BIGINT NOT NULL REFERENCES raw_rd_usp_vicell.run(id) ON DELETE CASCADE,
            bin_index       SMALLINT NOT NULL,
            bin_center      NUMERIC(6,4) NOT NULL,
            total_count     INTEGER NOT NULL,
            viable_count    INTEGER NOT NULL,
            CONSTRAINT uq_circ_dist_run_bin UNIQUE (run_id, bin_index)
        )
        """
    )

    # 6. run_cluster — 细胞团大小分布（29 bins/样本）
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.run_cluster (
            id              BIGSERIAL PRIMARY KEY,
            run_id          BIGINT NOT NULL REFERENCES raw_rd_usp_vicell.run(id) ON DELETE CASCADE,
            cluster_size    SMALLINT NOT NULL,
            count           INTEGER NOT NULL,
            CONSTRAINT uq_cluster_run_size UNIQUE (run_id, cluster_size)
        )
        """
    )

    # 7. etl_log — ETL 运行日志
    op.execute(
        """
        CREATE TABLE raw_rd_usp_vicell.etl_log (
            id              BIGSERIAL PRIMARY KEY,
            run_started_at  TIMESTAMPTZ NOT NULL,
            run_finished_at TIMESTAMPTZ,
            status          TEXT NOT NULL,
            files_scanned   INTEGER DEFAULT 0,
            files_loaded    INTEGER DEFAULT 0,
            files_skipped   INTEGER DEFAULT 0,
            files_errored   INTEGER DEFAULT 0,
            error_details   JSONB,
            watermark_before TIMESTAMPTZ,
            watermark_after  TIMESTAMPTZ
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA raw_rd_usp_vicell CASCADE")
