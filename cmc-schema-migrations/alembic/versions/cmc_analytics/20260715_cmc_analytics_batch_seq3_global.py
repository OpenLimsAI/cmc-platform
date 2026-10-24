"""cmc_analytics: 年流水号改「全局 3 位」——批号 YYSEQ 4→5 位（2026-07-15）

发号规则变更：年流水号 SEQ 从「每个项目各自 01–99」改成「全实验室按年的
**全局连续流水**」，且宽度 2→3 位。于是 26 年第 1 个登记的实验（不论哪个项目）
= 007-26001，第 2 个 = 008-26002（不再是 008-26001）。

结构改动：
  - batch_seq_counter：计数键 (project_code, year_yy) → 仅 (year_yy)。
    去掉项目维度＝全局年流水；「哪个项目占了哪个号」照旧由 batch_register 记录，
    计数器只记「今年发到第几号」。
  - batch_register.seq：char(2) → char(3)。
  - ck_batch_register_core_format：核心号正则 ^\\d{3}-\\d{4}$ → ^\\d{3}-\\d{5}$。

⚠️ 兼容性：旧 4 位格式的历史批号（如 007-2601）不满足新正则，ADD CONSTRAINT 会
校验既有行。若目标库残留旧格式测试数据，需先清掉再 upgrade（本系统 2026-07-11 才建、
仍属开发期，Mac 为空表）。年流水号无法从旧「按项目」计数机械换算成正确的全局序，
故计数器按「各项目当年已发数之和」作安全下界续号，不回填历史批号。

Revision ID: cmc_analytics_batch_seq3_global
Revises: cmc_analytics_batch_startdate
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_seq3_global"
down_revision = "cmc_analytics_batch_startdate"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"

# v_batch_dim 依赖 batch_register.seq，改列型前须先 DROP、改完再原样重建。
# 定义与位宽无关，故 upgrade/downgrade 复用同一份（取自改动前的现网视图定义）。
_V_BATCH_DIM = """
CREATE VIEW batch.v_batch_dim AS
SELECT (r.business_batch_no::text || '-'::text) || v.stage_code::text AS vessel_key,
    r.business_batch_no AS batch_no,
    r.project_code,
    r.project_ref,
    r.project_source,
    r.year_yy,
    r.seq,
    v.stage_code,
    v.kind,
    v.train_stage AS generation,
    COALESCE(v.bioreactor_id,
        CASE
            WHEN v.kind::text = 'production_reactor'::text THEN v.stage_code
            ELSE NULL::character varying
        END) AS bioreactor_id,
    v.planned_days,
    v.status,
    r.campaign_type AS culture_campaign,
    r.gen_date,
    ((((r.project_code::text || '_'::text) || r.year_yy::text) || r.seq::text) || '_'::text) || v.stage_code::text AS batch_key,
    ( SELECT string_agg(p.stage_code::text, ','::text ORDER BY (p.stage_code::text)) AS string_agg
           FROM batch.batch_vessel_genealogy g
             JOIN batch.batch_vessel p ON p.vessel_id = g.parent_vessel_id
          WHERE g.child_vessel_id = v.vessel_id) AS seeded_from_stages
   FROM batch.batch_vessel v
     JOIN batch.batch_register r ON r.batch_id = v.batch_id
"""


def _rebuild_v_batch_dim() -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")


def _recreate_v_batch_dim() -> None:
    op.execute(_V_BATCH_DIM)
    op.execute(f"GRANT SELECT ON batch.v_batch_dim TO {_READERS}")


def upgrade() -> None:
    # v_batch_dim 依赖 seq 列，先删（改完列再重建）
    _rebuild_v_batch_dim()

    # ---- 批号核心号：seq 位宽 + 正则 4→5 位 ----
    op.execute(
        "ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format"
    )
    op.execute("ALTER TABLE batch.batch_register ALTER COLUMN seq TYPE char(3)")

    # 既有旧 4 位批号（proj-YYSS）机械补零到 5 位（proj-YY0SS），并把 seq 补到 3 位。
    # 只保留数字身份、不重排全局序：007-2602 → 007-26002。满足新正则、不丢数据。
    op.execute(
        """
        UPDATE batch.batch_register
        SET business_batch_no = substr(business_batch_no, 1, 3) || '-'
                              || substr(business_batch_no, 5, 2) || '0'
                              || substr(business_batch_no, 7, 2),
            seq = lpad(trim(seq), 3, '0')
        WHERE business_batch_no ~ '^[0-9]{3}-[0-9]{4}$'
        """
    )

    op.execute(
        """
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '^[0-9]{3}-[0-9]{5}$')
        """
    )

    # ---- 计数器：(项目+年) → 仅按年（全局年流水）----
    # 播种下界取「当年 batch_register 已用的最大流水号」——与旧计数表状态无关、
    # 抗 downgrade/upgrade 往返，保证续号绝不撞已发出的号（业务批号 UNIQUE）。
    op.execute(
        """
        CREATE TABLE batch.batch_seq_counter_new (
            year_yy  char(2) NOT NULL,
            last_seq integer  NOT NULL DEFAULT 0,
            PRIMARY KEY (year_yy)
        )
        """
    )
    op.execute(
        """
        INSERT INTO batch.batch_seq_counter_new (year_yy, last_seq)
        SELECT year_yy, COALESCE(MAX(seq::int), 0)
        FROM batch.batch_register
        GROUP BY year_yy
        """
    )
    op.execute("DROP TABLE batch.batch_seq_counter")
    op.execute("ALTER TABLE batch.batch_seq_counter_new RENAME TO batch_seq_counter")

    # 列型改完，原样重建视图 + 恢复授权
    _recreate_v_batch_dim()


def downgrade() -> None:
    # 结构回滚。数据尽力反向：流水 ≤99 的行可去掉补零回到 4 位；
    # 流水 ≥100 的行无法塞回旧 2 位宽，会在下面 ALTER/约束处报错（此时需人工处理）。
    _rebuild_v_batch_dim()

    op.execute(
        "ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format"
    )
    op.execute(
        """
        UPDATE batch.batch_register
        SET business_batch_no = substr(business_batch_no, 1, 3) || '-'
                              || substr(business_batch_no, 5, 2)
                              || substr(business_batch_no, 8, 2),
            seq = substr(seq, 2, 2)
        WHERE business_batch_no ~ '^[0-9]{3}-[0-9]{2}0[0-9]{2}$'
        """
    )
    op.execute("ALTER TABLE batch.batch_register ALTER COLUMN seq TYPE char(2)")
    op.execute(
        """
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '^[0-9]{3}-[0-9]{4}$')
        """
    )

    _recreate_v_batch_dim()

    op.execute(
        """
        CREATE TABLE batch.batch_seq_counter_old (
            project_code varchar(16) NOT NULL,
            year_yy      char(2)     NOT NULL,
            last_seq     integer     NOT NULL DEFAULT 0,
            PRIMARY KEY (project_code, year_yy)
        )
        """
    )
    op.execute("DROP TABLE batch.batch_seq_counter")
    op.execute("ALTER TABLE batch.batch_seq_counter_old RENAME TO batch_seq_counter")
