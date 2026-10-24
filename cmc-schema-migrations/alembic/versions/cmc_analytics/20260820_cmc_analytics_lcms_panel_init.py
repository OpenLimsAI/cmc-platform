"""cmc_analytics: 新建应用 schema lcms_panel(LC-MS/MS 靶向定量解析看板)

依据 lcms-panel-explorer/docs/01-architecture-decisions.md(阶段三 ADR):
- D1:应用工作表不进 mart(非 BI 星型模型),仿 batch/mdm 先例开独立 schema;
  待负责人在白皮书下一版 §2.3 登记。
- D2:compound 为面板配置快照(每上传一份),预留 substance_code 挂 MDM Substance。
- D4:一次 txt 上传叫 upload_batch;injection.batch_id 预留给公司既有批号。
- E1:统一表骨架(BIGINT IDENTITY 主键、TIMESTAMPTZ、status 带 CHECK)。
- E2(负责人 2026-08-20 裁决):操作人按总纲 §8.2 字符串快照,不建人员表。
- E3:lcms_panel.access_audit_log 字段对齐 cmc_rd.meta.access_audit_log。
- E4:watermark 不适用(人工上传);file_sha256 幂等 + superseded_by 支持重解析。

Revision ID: cmc_analytics_lcms_panel_init
Revises: cmc_analytics_batch_legacy_no
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_lcms_panel_init"
down_revision = "cmc_analytics_batch_legacy_no"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS lcms_panel")

    op.execute("""
        CREATE TABLE lcms_panel.upload_batch (
            upload_batch_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            file_name        TEXT NOT NULL,
            file_sha256      VARCHAR(64) NOT NULL,
            status           VARCHAR(32) NOT NULL DEFAULT 'parsing'
                             CHECK (status IN ('parsing', 'ready', 'failed')),
            n_calibration_block INTEGER,
            n_result_row     INTEGER,
            n_result_col     INTEGER,
            r2_reproduction_median_dev DOUBLE PRECISION,
            acquisition_start TIMESTAMPTZ,
            acquisition_end   TIMESTAMPTZ,
            rt_drift_grows_with_rt BOOLEAN,
            dilution_overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
            dilution_warnings  JSONB NOT NULL DEFAULT '[]'::jsonb,
            thresholds_snapshot JSONB NOT NULL,
            -- 同一 sha256 重新解析时,旧批次由新批次接替(E4)
            superseded_by    BIGINT REFERENCES lcms_panel.upload_batch(upload_batch_id),
            error_message    TEXT,
            created_by_username VARCHAR(64),
            created_by_name  VARCHAR(128),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_upload_batch_sha256 ON lcms_panel.upload_batch (file_sha256)")

    op.execute("""
        CREATE TABLE lcms_panel.injection (
            injection_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            upload_batch_id  BIGINT NOT NULL
                             REFERENCES lcms_panel.upload_batch(upload_batch_id) ON DELETE CASCADE,
            sample_name      TEXT NOT NULL,
            sample_type      VARCHAR(32) NOT NULL,
            sample_comment   TEXT,
            acquisition_date TIMESTAMPTZ,
            file_name        TEXT,
            rack_position    TEXT,
            vial_position    TEXT,
            dilution_factor_file      DOUBLE PRECISION,
            dilution_factor_effective DOUBLE PRECISION,
            -- 公司既有批号(总纲 §4 / C05),现阶段为空,未来关联生产批次时填入
            batch_id         VARCHAR(32),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (upload_batch_id, sample_name)
        )
    """)

    op.execute("""
        CREATE TABLE lcms_panel.compound (
            compound_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            upload_batch_id  BIGINT NOT NULL
                             REFERENCES lcms_panel.upload_batch(upload_batch_id) ON DELETE CASCADE,
            -- 导出文件里的原始峰名,永远原样展示
            peak_name_raw    TEXT NOT NULL,
            name_normalized  TEXT NOT NULL,
            match_status     VARCHAR(32) NOT NULL
                             CHECK (match_status IN ('matched', 'unmatched', 'non_compound')),
            -- 命中分类表时的快照(未命中为 NULL,但行必须存在=未匹配峰可见)
            taxonomy_name    TEXT,
            chinese_name     TEXT,
            chem_class       TEXT,
            pathway          TEXT,
            polarity         VARCHAR(16),
            -- 预留:未来挂 MDM Substance 域(ADR D2)
            substance_code   VARCHAR(32),
            transition       TEXT,
            internal_standard TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (upload_batch_id, peak_name_raw)
        )
    """)

    op.execute("""
        CREATE TABLE lcms_panel.calibration (
            calibration_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            compound_id      BIGINT NOT NULL UNIQUE
                             REFERENCES lcms_panel.compound(compound_id) ON DELETE CASCADE,
            -- 厂商导出参数(原样)
            fit_type         VARCHAR(32),
            weighting        VARCHAR(32),
            use_signal       VARCHAR(16),
            vendor_intercept DOUBLE PRECISION,
            vendor_slope     DOUBLE PRECISION,
            vendor_r         DOUBLE PRECISION,
            vendor_r2        DOUBLE PRECISION,
            -- 复现与重拟合(算法 2.1/2.2)
            n_points         INTEGER NOT NULL DEFAULT 0,
            r2_recomputed    DOUBLE PRECISION,
            full_intercept   DOUBLE PRECISION,
            full_slope       DOUBLE PRECISION,
            window_n         INTEGER NOT NULL DEFAULT 0,
            window_lo        DOUBLE PRECISION,
            window_hi        DOUBLE PRECISION,
            window_intercept DOUBLE PRECISION,
            window_slope     DOUBLE PRECISION,
            window_max_dev_pct DOUBLE PRECISION,
            accuracy_pct     JSONB NOT NULL DEFAULT '[]'::jsonb,
            -- 2.3 饱和 / 2.4 BEC / 免拟合响应因子(阶段五稀释优化要用)
            bec              DOUBLE PRECISION,
            bec_exceeds_lloq BOOLEAN NOT NULL DEFAULT FALSE,
            saturating       BOOLEAN NOT NULL DEFAULT FALSE,
            top_step_recovery_pct DOUBLE PRECISION,
            dynamic_range    DOUBLE PRECISION,
            nominal_range    DOUBLE PRECISION,
            saturation_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
            rf_plateau_n     INTEGER NOT NULL DEFAULT 0,
            rf_plateau_lo    DOUBLE PRECISION,
            rf_plateau_hi    DOUBLE PRECISION,
            rf               DOUBLE PRECISION,
            verdict          VARCHAR(64),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE lcms_panel.measurement (
            measurement_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            injection_id     BIGINT NOT NULL
                             REFERENCES lcms_panel.injection(injection_id) ON DELETE CASCADE,
            compound_id      BIGINT NOT NULL
                             REFERENCES lcms_panel.compound(compound_id) ON DELETE CASCADE,
            area             DOUBLE PRECISION,
            height           DOUBLE PRECISION,
            nominal_conc     DOUBLE PRECISION,
            vendor_conc      DOUBLE PRECISION,
            refit_conc       DOUBLE PRECISION,
            rt               DOUBLE PRECISION,
            expected_rt      DOUBLE PRECISION,
            signal_to_noise  DOUBLE PRECISION,
            peak_width       DOUBLE PRECISION,
            asymmetry        DOUBLE PRECISION,
            integration_quality DOUBLE PRECISION,
            accuracy_pct     DOUBLE PRECISION,
            use_record       BOOLEAN,
            in_window        BOOLEAN,
            reliability      VARCHAR(32) NOT NULL DEFAULT 'no_valid_curve'
                             CHECK (reliability IN ('quantifiable', 'above_uloq', 'below_lloq',
                                                    'no_valid_curve', 'integration_failed', 'excluded')),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (injection_id, compound_id)
        )
    """)
    op.execute("CREATE INDEX idx_measurement_compound ON lcms_panel.measurement (compound_id)")

    op.execute("""
        CREATE TABLE lcms_panel.qc_finding (
            qc_finding_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            upload_batch_id  BIGINT NOT NULL
                             REFERENCES lcms_panel.upload_batch(upload_batch_id) ON DELETE CASCADE,
            -- 算法编号:'2.1'…'2.9' / 'sequence' / 'parse_selfcheck'
            algorithm        VARCHAR(32) NOT NULL,
            level            VARCHAR(16) NOT NULL
                             CHECK (level IN ('red', 'yellow', 'green', 'info')),
            subject_type     VARCHAR(32) NOT NULL
                             CHECK (subject_type IN ('batch', 'compound', 'injection',
                                                     'compound_pair', 'measurement')),
            -- 作用对象引用:compound_pair 存两个化合物名(ADR 缺口 2)
            subject_ref      JSONB NOT NULL,
            -- 判定依据:命中的规则、当时阈值、实测值(brief §6 可追溯)
            evidence         JSONB NOT NULL,
            advice           TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_qc_finding_batch ON lcms_panel.qc_finding (upload_batch_id, algorithm)")

    op.execute("""
        CREATE TABLE lcms_panel.access_audit_log (
            access_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            access_time      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_name        TEXT,
            client_addr      INET,
            session_id       TEXT,
            access_type      TEXT,
            query_text       TEXT,
            target_objects   JSONB,
            rows_returned    BIGINT
        )
    """)
    op.execute("CREATE INDEX idx_lcms_access_audit_time ON lcms_panel.access_audit_log (access_time)")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS lcms_panel CASCADE")
