"""cmc_analytics: batch 数据模型 v2 —— 批号=实验核心号，容器为子实体（2026-07-11）

纠正 v1 的建模错误：v1 把罐号塞进了批号（007-2601-A1，每容器一个批号），
与命名速查文档冲突。权威规则：**批号 = 一次实验一个核心号 007-2601（全程不变）**，
S1/S2a/N1/A1 是**样品名里的阶段码**、是批号下的容器子实体，不是批号本身。

改动：
- batch_register 改为「实验级」：business_batch_no = 核心号（^\\d{3}-\\d{4}$），一实验一行。
- 新增 batch_vessel：一容器一行（阶段码/kind/代次/物理罐/拟定天数/parent 谱系/状态）。
- 状态历史、谱系、维度视图、样品名→键 函数 全部改到容器粒度。
- fn_sample_to_batch 返回「核心号+阶段码」=容器键（剥 -D##[-T#]）。

Revision ID: cmc_analytics_batch_model_v2
Revises: cmc_analytics_batch_mdm_snap
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_model_v2"
down_revision = "cmc_analytics_batch_mdm_snap"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"
_STAGE_RE = "^([SN][0-9]+[a-z]?|(SF|ST|A|B|C|R)[0-9]{1,2}|(HV|CAP|VI|POL|UF|DS))$"


def upgrade() -> None:
    # ---- 拆掉 v1 的每容器批号模型 ----
    op.execute("DROP VIEW IF EXISTS batch.v_batch_lineage")
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_sample_to_batch(text)")
    op.execute("DROP TRIGGER IF EXISTS trg_batch_status_change ON batch.batch_register")
    op.execute("DROP TRIGGER IF EXISTS trg_batch_status_init ON batch.batch_register")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_batch_status_history()")
    op.execute("DROP TABLE IF EXISTS batch.batch_status_history")
    op.execute("DROP TABLE IF EXISTS batch.batch_genealogy")
    op.execute("DROP TABLE IF EXISTS batch.batch_register")

    # ---- 实验级批号表（业务批号 = 核心号）----
    op.execute(
        """
        CREATE TABLE batch.batch_register (
            batch_id          bigserial   PRIMARY KEY,
            business_batch_no varchar(16) NOT NULL UNIQUE,           -- 核心号，如 007-2601
            project_code      varchar(16) NOT NULL,
            project_ref       varchar(64) NOT NULL,
            project_source    varchar(8)  NOT NULL DEFAULT 'manual',
            year_yy           char(2)     NOT NULL,
            seq               char(2)     NOT NULL,
            campaign_type     varchar(16),
            gen_date          date        NOT NULL DEFAULT current_date,
            created_by        varchar(64) NOT NULL DEFAULT 'system',
            created_at        timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_batch_register_core_format
              CHECK (business_batch_no ~ '^[0-9]{3}-[0-9]{4}$'),
            CONSTRAINT ck_batch_register_source
              CHECK (project_source IN ('manual','mdm'))
        )
        """
    )

    # ---- 容器子实体表 ----
    op.execute(
        f"""
        CREATE TABLE batch.batch_vessel (
            vessel_id       bigserial   PRIMARY KEY,
            batch_id        bigint      NOT NULL REFERENCES batch.batch_register(batch_id) ON DELETE CASCADE,
            stage_code      varchar(8)  NOT NULL,                    -- 样品名阶段码：S1/S2a/N1/A1…
            kind            varchar(24) NOT NULL,                    -- flask / seed_reactor / production_reactor / dsp
            seed_level      integer,                                 -- 摇瓶级：1,2,3…（flask 用）
            train_stage     varchar(8),                              -- N-2/N-1/N（罐用）
            equipment_ref   varchar(32),                             -- 物理设备
            planned_days    integer,                                 -- 拟定扩增天数（仅入库、不进名字）
            parent_vessel_id bigint     REFERENCES batch.batch_vessel(vessel_id),  -- seeded_from 父容器
            status          varchar(16) NOT NULL DEFAULT 'issued',
            created_by      varchar(64) NOT NULL DEFAULT 'system',
            created_at      timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_batch_vessel_stage UNIQUE (batch_id, stage_code),
            CONSTRAINT ck_batch_vessel_stage_format CHECK (stage_code ~ '{_STAGE_RE}'),
            CONSTRAINT ck_batch_vessel_no_self CHECK (parent_vessel_id <> vessel_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_batch_vessel_batch_id ON batch.batch_vessel(batch_id)")

    # ---- 容器状态历史（审计）----
    op.execute(
        """
        CREATE TABLE batch.batch_vessel_status_history (
            id          bigserial   PRIMARY KEY,
            vessel_id   bigint      NOT NULL REFERENCES batch.batch_vessel(vessel_id) ON DELETE CASCADE,
            old_status  varchar(16),
            new_status  varchar(16) NOT NULL,
            changed_by  varchar(64) NOT NULL DEFAULT 'system',
            changed_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION batch.fn_vessel_status_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE actor text := coalesce(nullif(current_setting('batch.actor', true), ''), 'system');
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO batch.batch_vessel_status_history(vessel_id, old_status, new_status, changed_by)
                VALUES (NEW.vessel_id, NULL, NEW.status, actor);
            ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO batch.batch_vessel_status_history(vessel_id, old_status, new_status, changed_by)
                VALUES (NEW.vessel_id, OLD.status, NEW.status, actor);
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_vessel_status_init AFTER INSERT ON batch.batch_vessel "
        "FOR EACH ROW EXECUTE FUNCTION batch.fn_vessel_status_history()"
    )
    op.execute(
        "CREATE TRIGGER trg_vessel_status_change AFTER UPDATE OF status ON batch.batch_vessel "
        "FOR EACH ROW EXECUTE FUNCTION batch.fn_vessel_status_history()"
    )

    # ---- 样品名 → 容器键（剥 -D##[-T#]，得 核心号+阶段码）----
    op.execute(
        """
        CREATE OR REPLACE FUNCTION batch.fn_sample_to_batch(sample_name text)
        RETURNS text LANGUAGE sql IMMUTABLE AS $$
          SELECT regexp_replace(sample_name, '-D[0-9]{1,2}(-T[0-9]+)?$', '');
        $$
        """
    )

    # ---- 看板维度视图（一容器一行）----
    op.execute(
        """
        CREATE VIEW batch.v_batch_dim AS
        SELECT
            (r.business_batch_no || '-' || v.stage_code)  AS vessel_key,      -- 007-2601-A1（样品 JOIN 键）
            r.business_batch_no                            AS batch_no,        -- 007-2601（真批号）
            r.project_code, r.project_ref, r.project_source, r.year_yy, r.seq,
            v.stage_code                                   AS bioreactor_id,
            v.kind,
            v.train_stage                                  AS generation,
            v.equipment_ref,
            v.planned_days,
            v.status,
            r.campaign_type                                AS culture_campaign,
            r.gen_date,
            (r.project_code || '_' || r.year_yy || r.seq || '_' || v.stage_code) AS batch_key,
            p.stage_code                                   AS seeded_from_stage,
            CASE WHEN p.stage_code IS NOT NULL
                 THEN (r.business_batch_no || '-' || p.stage_code) END        AS seeded_from_vessel_key
        FROM batch.batch_vessel v
        JOIN batch.batch_register r ON r.batch_id = v.batch_id
        LEFT JOIN batch.batch_vessel p ON p.vessel_id = v.parent_vessel_id
        """
    )
    op.execute(
        """
        CREATE VIEW batch.v_batch_lineage AS
        SELECT
            (r.business_batch_no || '-' || p.stage_code) AS parent_vessel_key,
            (r.business_batch_no || '-' || c.stage_code) AS child_vessel_key,
            'seeded_from' AS relation
        FROM batch.batch_vessel c
        JOIN batch.batch_vessel p ON p.vessel_id = c.parent_vessel_id
        JOIN batch.batch_register r ON r.batch_id = c.batch_id
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA batch TO {_READERS}")
    op.execute(f"GRANT SELECT ON batch.v_batch_dim, batch.v_batch_lineage TO {_READERS}")
    op.execute(f"GRANT EXECUTE ON FUNCTION batch.fn_sample_to_batch(text) TO {_READERS}")


def downgrade() -> None:
    # 回到 v1 每容器批号模型（结构，不还原数据）
    op.execute("DROP VIEW IF EXISTS batch.v_batch_lineage")
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_sample_to_batch(text)")
    op.execute("DROP TRIGGER IF EXISTS trg_vessel_status_change ON batch.batch_vessel")
    op.execute("DROP TRIGGER IF EXISTS trg_vessel_status_init ON batch.batch_vessel")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_vessel_status_history()")
    op.execute("DROP TABLE IF EXISTS batch.batch_vessel_status_history")
    op.execute("DROP TABLE IF EXISTS batch.batch_vessel")
    op.execute("DROP TABLE IF EXISTS batch.batch_register")

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
            CONSTRAINT ck_batch_register_source CHECK (project_source IN ('manual','mdm'))
        )
        """
    )
