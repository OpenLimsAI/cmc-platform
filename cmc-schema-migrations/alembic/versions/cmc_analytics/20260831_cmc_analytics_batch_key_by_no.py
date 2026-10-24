"""cmc_analytics: 批次身份 batch_key 改按批号拼 + 老规则批次年流水置空（2026-08-31）

背景：试用期补录的历史实验已后台改回真实老规则批号（如 016-R2601），但
  ① 它们的隐藏字段 seq（年流水）还留着系统当初发号的值（如 021）。新规则流水已
     从 001 重数，将来同项目再排到 021 时两批 seq 相同——批号不撞（UNIQUE），
     但按 project_year_seq 拼的 batch_key 会撞。
  ② 下游看板（cmc-rd-usp-dashboard vicell/nova）从仪器样品名拆出的批次身份是
     「项目_批号中段_罐号」，老规则样品拆出 016_R2601_B3，而 v_batch_dim 拼的是
     016_26021_B3，21 个 R 号批次一直关联不上。

改动：
  - batch_register.seq 放开 NOT NULL；老规则批号（非 PROJ-YYSEQ 形态）的 seq 置空
    ——它们不是系统发的号，本就不该占年流水；今后流水与批号严格一致。
  - v_batch_dim.batch_key 改为 replace(business_batch_no,'-','_') || '_' || stage_code：
    新规则 0092_26001_A6、老规则 016_R2601_B3，与仪器侧一致且天然唯一。
    其余列不变（保留 seq 列，老规则为 NULL）。

Revision ID: cmc_analytics_batch_key_by_no
Revises: cmc_analytics_lcms_panel_rawarc
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_key_by_no"
down_revision = "cmc_analytics_lcms_panel_rawarc"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"
_NEW_RULE_RE = "^[A-Za-z0-9]+-[0-9]{5}$"

_VIEW_HEAD = """
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
"""
_VIEW_TAIL = """
    ( SELECT string_agg(p.stage_code::text, ','::text ORDER BY (p.stage_code::text)) AS string_agg
           FROM batch.batch_vessel_genealogy g
             JOIN batch.batch_vessel p ON p.vessel_id = g.parent_vessel_id
          WHERE g.child_vessel_id = v.vessel_id) AS seeded_from_stages
   FROM batch.batch_vessel v
     JOIN batch.batch_register r ON r.batch_id = v.batch_id
"""
_KEY_BY_NO = (
    "    replace(r.business_batch_no::text, '-', '_') || '_' || v.stage_code::text AS batch_key,"
)
_KEY_BY_SEQ = (
    "    ((((r.project_code::text || '_'::text) || r.year_yy::text) || r.seq::text) || '_'::text)"
    " || v.stage_code::text AS batch_key,"
)


def _recreate_view(key_expr: str) -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute(_VIEW_HEAD + key_expr + _VIEW_TAIL)
    op.execute(f"GRANT SELECT ON batch.v_batch_dim TO {_READERS}")


def upgrade() -> None:
    op.execute("ALTER TABLE batch.batch_register ALTER COLUMN seq DROP NOT NULL")
    op.execute(
        f"UPDATE batch.batch_register SET seq = NULL WHERE business_batch_no !~ '{_NEW_RULE_RE}'"
    )
    _recreate_view(_KEY_BY_NO)


def downgrade() -> None:
    # 老规则批次的 seq 无法还原原值（已置空且无业务意义），回填 '000' 以满足 NOT NULL。
    _recreate_view(_KEY_BY_SEQ)
    op.execute("UPDATE batch.batch_register SET seq = '000' WHERE seq IS NULL")
    op.execute("ALTER TABLE batch.batch_register ALTER COLUMN seq SET NOT NULL")
