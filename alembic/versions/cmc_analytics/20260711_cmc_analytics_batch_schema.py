"""cmc_analytics: 研发批号登记系统 batch schema —— 发号/登记/谱系（2026-07-11）

新增域 `batch`（rd-batch-registry 应用的事务型登记表；批次是事务数据，进 cmc_analytics，
不进 cmc_rd 只读层、不进 cmab_mdm）。四张表：
  - batch_seq_counter    并发安全发号计数器（短项目码 + 年）
  - batch_register       批次登记主表（业务批号唯一 + 正则 CHECK）
  - batch_genealogy      谱系父子边
  - batch_status_history 状态历史（审计）

Revision ID: cmc_analytics_batch_schema
Revises: cmc_analytics_vicell_read_grant
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_schema"
down_revision = "cmc_analytics_vicell_read_grant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS batch")

    op.execute(
        """
        CREATE TABLE batch.batch_seq_counter (
            project_code varchar(16) NOT NULL,
            year_yy      char(2)     NOT NULL,
            last_seq     integer     NOT NULL DEFAULT 0,
            PRIMARY KEY (project_code, year_yy)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE batch.batch_register (
            batch_id          bigserial   PRIMARY KEY,
            business_batch_no varchar(40) NOT NULL UNIQUE,
            project_code      varchar(16) NOT NULL,
            project_ref       varchar(64) NOT NULL,
            project_source    varchar(8)  NOT NULL DEFAULT 'manual',
            year_yy           char(2)     NOT NULL,
            seq               char(2)     NOT NULL,
            stage_code        varchar(6)  NOT NULL,
            suffix            varchar(6),
            campaign_type     varchar(16),
            train_stage       varchar(8),
            equipment_ref     varchar(32),
            gen_date          date        NOT NULL DEFAULT current_date,
            status            varchar(16) NOT NULL DEFAULT 'issued',
            created_by        varchar(64) NOT NULL DEFAULT 'system',
            created_at        timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_batch_register_no_format
              CHECK (business_batch_no ~ '^[0-9]{3}-[0-9]{4}-[A-Z]{1,3}[0-9]{0,2}(-(RW|RP|PL)[0-9])?$'),
            CONSTRAINT ck_batch_register_source
              CHECK (project_source IN ('manual','mdm'))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE batch.batch_genealogy (
            parent_batch_id bigint      NOT NULL REFERENCES batch.batch_register(batch_id),
            child_batch_id  bigint      NOT NULL REFERENCES batch.batch_register(batch_id),
            relation        varchar(16) NOT NULL,
            created_at      timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (parent_batch_id, child_batch_id, relation),
            CONSTRAINT ck_batch_genealogy_no_self CHECK (parent_batch_id <> child_batch_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE batch.batch_status_history (
            id          bigserial   PRIMARY KEY,
            batch_id    bigint      NOT NULL REFERENCES batch.batch_register(batch_id),
            old_status  varchar(16),
            new_status  varchar(16) NOT NULL,
            changed_by  varchar(64) NOT NULL DEFAULT 'system',
            changed_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch.batch_status_history")
    op.execute("DROP TABLE IF EXISTS batch.batch_genealogy")
    op.execute("DROP TABLE IF EXISTS batch.batch_register")
    op.execute("DROP TABLE IF EXISTS batch.batch_seq_counter")
    op.execute("DROP SCHEMA IF EXISTS batch")
