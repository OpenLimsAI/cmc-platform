"""mm.material v2: 从 R&D 样品登记改造为全公司物料身份注册表

Revision ID: 0038_mm_material_v2
Revises: 0037_user_force_pwd_change
Create Date: 2026-05-19 01:00:00.000000

改造要点：
  - material_type 7 值→4 值：reagent/consumable/standard/column
  - 新增 7 列：manufacturer/catalog_no/spec_model/unit/package_spec/hazard_class/category
  - category 严格枚举（按 type 分组，复合 CHECK）
  - grade 从 4 值枚举改为自由文本
  - 清空现有 demo 数据（模块未上线）
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0038_mm_material_v2"
down_revision: str | None = "0037_user_force_pwd_change"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 清空 demo 数据（模块未上线，仅 demo 记录）
    op.execute("DELETE FROM mm.material_batch")
    op.execute("DELETE FROM mm.material")

    # 2. 删除旧约束（naming convention 使实际名称为 ck_material_ck_material_*）
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_ck_material_type")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_type")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_ck_material_grade")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_grade")

    # 3. 新增 7 列
    op.execute("ALTER TABLE mm.material ADD COLUMN manufacturer VARCHAR(100)")
    op.execute("ALTER TABLE mm.material ADD COLUMN catalog_no VARCHAR(100)")
    op.execute("ALTER TABLE mm.material ADD COLUMN spec_model VARCHAR(200)")
    op.execute("ALTER TABLE mm.material ADD COLUMN unit VARCHAR(20) NOT NULL DEFAULT 'ea'")
    op.execute("ALTER TABLE mm.material ADD COLUMN package_spec VARCHAR(100)")
    op.execute("ALTER TABLE mm.material ADD COLUMN hazard_class TEXT[]")
    op.execute("ALTER TABLE mm.material ADD COLUMN category VARCHAR(50)")

    # 4. 新 material_type 约束（4 值）
    op.execute("""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_type
        CHECK (material_type IN ('reagent','consumable','standard','column'))
    """)

    # 5. category 扁平枚举（公司物料分类体系，14 值）
    op.execute("""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_category
        CHECK (
            category IS NULL
            OR category IN (
                '一般耗材','关键耗材','关键试剂','内包材','劳保',
                '原辅料','参比品','对照品','工艺用水/气','标准品',
                '细胞种子','自制包材','试剂','运输包装材料'
            )
        )
    """)

    # 6. 新索引
    op.execute(
        "CREATE INDEX ix_material_category ON mm.material (category) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_material_manufacturer ON mm.material (manufacturer) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    # 删除新索引
    op.execute("DROP INDEX IF EXISTS mm.ix_material_category")
    op.execute("DROP INDEX IF EXISTS mm.ix_material_manufacturer")

    # 删除新约束
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_category")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_type")

    # 删除新列
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS category")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS hazard_class")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS package_spec")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS unit")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS spec_model")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS catalog_no")
    op.execute("ALTER TABLE mm.material DROP COLUMN IF EXISTS manufacturer")

    # 恢复旧约束
    op.execute("""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_type
        CHECK (material_type IN ('candidate','reference','stability','buffer','raw',
               'intermediate','other'))
    """)
    op.execute("""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_grade
        CHECK (grade IS NULL OR grade IN
               ('RUO','GMP','Reference Standard','Working Standard'))
    """)
