"""PRS 对齐 SMP-RD-NUM-001 V2.1 第一批（A1/A2/A3）

Revision ID: 0047_prs_smp_v21_batch1
Revises: 0046_role_code_partial_unique
Create Date: 2026-07-15 01:00:00.000000

SMP-RD-NUM-001 V2.1 差异整改第一批（低风险）：
- A1 §7.1 / 附录 A：项目编号加公司全局前缀 CMAB
      PRJ-YYYY-NNNN → CMAB-PRJ-YYYY-NNNN
- A2 §11.3：项目状态机补 cancelled（立项后未启动即取消）
- A3 §7.4(c)：project_type 取值对齐 SMP 执行类型集合
      旧：cmc/preclinical/clinical/regulatory/commercial/platform/other
      新：discovery/nonclinical/cmc/clinical/regulatory/translational/mixed
      （沿用本库全小写枚举惯例，不照搬 SMP CamelCase）

数据现状：PRS 项目真实数据 0 条，仅做防御性 remap。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0047_prs_smp_v21_batch1"
down_revision: str | None = "0046_role_code_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A3 新旧取值集合
_OLD_PROJECT_TYPES = ("cmc", "preclinical", "clinical", "regulatory", "commercial", "platform", "other")
_NEW_PROJECT_TYPES = ("discovery", "nonclinical", "cmc", "clinical", "regulatory", "translational", "mixed")


def upgrade() -> None:
    # ============== A1：编号前缀 PRJ- → CMAB-PRJ- ==============
    # 1) 重建按年发号触发器，prefix 传 'CMAB-PRJ-'
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_assign_code()
        RETURNS TRIGGER AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('project', 'CMAB-PRJ-', v_year, 4);
                NEW.project_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    # 2) 已创建的年度序列行回改前缀（幂等：仅改仍是 PRJ- 开头的）
    op.execute("""
        UPDATE meta.code_sequence
           SET prefix = 'CMAB-' || prefix
         WHERE sequence_name LIKE 'project_%'
           AND prefix LIKE 'PRJ-%';
    """)

    # ============== A2：project_status 补 cancelled ==============
    # 注：本库 metadata 命名约定使实际约束名为 ck_project_ck_project_status（双前缀）；
    # 两个可能名都 drop 以求幂等，重建时沿用约定的双前缀名。
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_status")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_status")
    op.execute("""
        ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_status
        CHECK (status IN ('proposed','initiated','active','on_hold','completed','terminated','cancelled'))
    """)
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order)
        VALUES ('project_status', 'cancelled', '已取消', 'Cancelled', 70)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
    """)

    # ============== A3：project_type 取值对齐 ==============
    # 1) 防御性 remap（真实数据 0 条；避免加新 CHECK 时被历史脏值卡住）
    op.execute("UPDATE prs.project SET project_type='nonclinical' WHERE project_type='preclinical'")
    _new_in = ",".join(f"'{v}'" for v in _NEW_PROJECT_TYPES)
    op.execute(f"UPDATE prs.project SET project_type='mixed' WHERE project_type NOT IN ({_new_in})")
    # 2) 换 CHECK（实际约束名为双前缀 ck_project_ck_project_type）
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_type")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_type")
    op.execute(f"""
        ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_type
        CHECK (project_type IN ({_new_in}))
    """)
    # 3) 换 lookup_value 展示字典
    op.execute("DELETE FROM meta.lookup_value WHERE lookup_type='project_type'")
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
            ('project_type', 'discovery',     '发现',   'Discovery',    10),
            ('project_type', 'nonclinical',   '非临床', 'Nonclinical',  20),
            ('project_type', 'cmc',           'CMC',    'CMC',          30),
            ('project_type', 'clinical',      '临床',   'Clinical',     40),
            ('project_type', 'regulatory',    '注册',   'Regulatory',   50),
            ('project_type', 'translational', '转化',   'Translational',60),
            ('project_type', 'mixed',         '混合',   'Mixed',        70)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
    """)


def downgrade() -> None:
    # A3 回退
    op.execute("DELETE FROM meta.lookup_value WHERE lookup_type='project_type'")
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
            ('project_type', 'cmc',         'CMC 项目', 'CMC Project', 10),
            ('project_type', 'preclinical', '临床前',   'Pre-Clinical', 20),
            ('project_type', 'clinical',    '临床',     'Clinical',     30),
            ('project_type', 'regulatory',  '注册',     'Regulatory',   40),
            ('project_type', 'commercial',  '商业化',   'Commercial',   50)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
    """)
    op.execute("UPDATE prs.project SET project_type='preclinical' WHERE project_type='nonclinical'")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_type")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_type")
    _old_in = ",".join(f"'{v}'" for v in _OLD_PROJECT_TYPES)
    op.execute("UPDATE prs.project SET project_type='other' "
               f"WHERE project_type NOT IN ({_old_in})")
    op.execute(f"ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_type "
               f"CHECK (project_type IN ({_old_in}))")

    # A2 回退
    op.execute("DELETE FROM meta.lookup_value WHERE lookup_type='project_status' AND lookup_code='cancelled'")
    op.execute("UPDATE prs.project SET status='terminated' WHERE status='cancelled'")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_status")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_status")
    op.execute("""
        ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_status
        CHECK (status IN ('proposed','initiated','active','on_hold','completed','terminated'))
    """)

    # A1 回退
    op.execute("""
        UPDATE meta.code_sequence
           SET prefix = substring(prefix FROM 6)
         WHERE sequence_name LIKE 'project_%'
           AND prefix LIKE 'CMAB-PRJ-%';
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_assign_code()
        RETURNS TRIGGER AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('project', 'PRJ-', v_year, 4);
                NEW.project_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
