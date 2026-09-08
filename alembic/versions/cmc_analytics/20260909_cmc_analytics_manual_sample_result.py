"""cmc_analytics: 人工录入的取样结果——新建 manual.sample_result + 写账号 usp_writer（2026-09-09）

背景：渗透压等指标仪器不联网，只能由试验员每天手工录入。USP 看板（cmc-rd-usp-dashboard）
加一个「渗透压录入」页：按日期列出当天在 Nova / Vi-CELL 上跑过的样品（批次、罐、培养天
自动带出），试验员只填数值。看板原则只读，本表是唯一的人工写入点。

设计（负责人 2026-09-09 定）：
  - 通用表：一行 = 某批次某培养天某指标的一次录入；先只有 osmolality，以后滴度/纯度等
    人工指标直接复用（metric_code 区分），不再建表。
  - 只追加不覆盖：改数就再存一行，取值时按 (batch_key, metric_code, culture_day) 取
    entered_at 最新一行（视图 mart.fact_manual_latest）。历史全留，谁何时改的都可查。
  - 录入人存工号 + 姓名快照（来自 MDM JWT），不建人员外键（铁律）。
  - 写账号 usp_writer：只对本表有 INSERT（无 UPDATE/DELETE，保证追加语义），密码由运维
    ALTER ROLE 设置；看板读仍走 lims_reader。

Revision ID: cmc_analytics_manual_sample
Revises: cmc_analytics_batch_plan_draft
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_manual_sample"
down_revision = "cmc_analytics_batch_plan_draft"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS manual")
    op.execute(
        "COMMENT ON SCHEMA manual IS '人工录入的数据（仪器不联网、只能手填的结果）；只追加不覆盖'"
    )
    op.execute(
        """
        CREATE TABLE manual.sample_result (
            result_id          bigserial PRIMARY KEY,
            batch_key          varchar(64)  NOT NULL,   -- 项目_批号_罐，与 fact_nova / fact_vicell 同一套身份
            culture_day        integer      NOT NULL,   -- 培养天（自动从当天仪器样品带出，不手填）
            sample_date        date         NOT NULL,   -- 取样日期
            metric_code        varchar(32)  NOT NULL DEFAULT 'osmolality',
            value              double precision NOT NULL,
            unit               varchar(16)  NOT NULL,   -- 如 mOsm/kg
            note               text,
            source_sample_ids  text,                    -- 溯源：当天该样品在仪器上的样本名
            entered_by         varchar(64)  NOT NULL,   -- 工号（MDM username）
            entered_by_name    varchar(128),
            entered_at         timestamptz  NOT NULL DEFAULT now(),
            CONSTRAINT ck_manual_sample_result_metric CHECK (metric_code IN ('osmolality'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_manual_sample_result_key ON manual.sample_result "
        "(batch_key, metric_code, culture_day, entered_at DESC)"
    )
    op.execute("CREATE INDEX ix_manual_sample_result_date ON manual.sample_result (sample_date)")
    op.execute(
        "COMMENT ON TABLE manual.sample_result IS "
        "'人工录入的取样结果（渗透压等）；只追加，改数=再存一行，取最新一行为准'"
    )

    # 看板取值用：每个 (批次, 指标, 培养天) 只留最新一行
    op.execute(
        """
        CREATE VIEW mart.fact_manual_latest AS
        SELECT DISTINCT ON (batch_key, metric_code, culture_day)
            result_id, batch_key, culture_day, sample_date, metric_code, value, unit,
            note, source_sample_ids, entered_by, entered_by_name, entered_at
        FROM manual.sample_result
        ORDER BY batch_key, metric_code, culture_day, entered_at DESC, result_id DESC
        """
    )
    op.execute(
        "COMMENT ON VIEW mart.fact_manual_latest IS "
        "'人工录入结果的最新值（每批次每指标每培养天一行）；看板生化曲线/数据表读这里'"
    )

    # 只读账号：能读新 schema 与视图
    op.execute(f"GRANT USAGE ON SCHEMA manual TO {_READERS}")
    op.execute(f"GRANT SELECT ON manual.sample_result TO {_READERS}")
    op.execute(f"GRANT SELECT ON mart.fact_manual_latest TO {_READERS}")

    # 写账号：只能往这一张表追加
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='usp_writer') THEN
            CREATE ROLE usp_writer LOGIN;  -- 密码由运维 ALTER ROLE 设置，不进 git
          END IF;
        END $$;
        """
    )
    op.execute("GRANT CONNECT ON DATABASE cmc_analytics TO usp_writer")
    op.execute("GRANT USAGE ON SCHEMA manual TO usp_writer")
    op.execute("GRANT SELECT, INSERT ON manual.sample_result TO usp_writer")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE manual.sample_result_result_id_seq TO usp_writer")


def downgrade() -> None:
    op.execute("REVOKE ALL ON manual.sample_result FROM usp_writer")
    op.execute("REVOKE ALL ON SEQUENCE manual.sample_result_result_id_seq FROM usp_writer")
    op.execute("REVOKE USAGE ON SCHEMA manual FROM usp_writer")
    op.execute("REVOKE CONNECT ON DATABASE cmc_analytics FROM usp_writer")
    op.execute("DROP VIEW IF EXISTS mart.fact_manual_latest")
    op.execute("DROP TABLE IF EXISTS manual.sample_result")
    op.execute("DROP SCHEMA IF EXISTS manual")
