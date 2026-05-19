"""mm.material ck_material_category 加 外包材（15 值）

Revision ID: 0039_mm_category_add_waibao
Revises: 0038_mm_material_v2
Create Date: 2026-05-19
"""
from alembic import op


revision = "0039_mm_category_add_waibao"
down_revision = "0038_mm_material_v2"
branch_labels = None
depends_on = None


NEW_CATEGORIES = (
    "'一般耗材','关键耗材','关键试剂','内包材','外包材','劳保',"
    "'原辅料','参比品','对照品','工艺用水/气','标准品',"
    "'细胞种子','自制包材','试剂','运输包装材料'"
)

OLD_CATEGORIES = (
    "'一般耗材','关键耗材','关键试剂','内包材','劳保',"
    "'原辅料','参比品','对照品','工艺用水/气','标准品',"
    "'细胞种子','自制包材','试剂','运输包装材料'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_category")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_ck_material_category")
    op.execute(
        f"""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_category
        CHECK (category IS NULL OR category IN ({NEW_CATEGORIES}))
        """
    )


def downgrade() -> None:
    op.execute("UPDATE mm.material SET category = NULL WHERE category = '外包材'")
    op.execute("ALTER TABLE mm.material DROP CONSTRAINT IF EXISTS ck_material_category")
    op.execute(
        f"""
        ALTER TABLE mm.material ADD CONSTRAINT ck_material_category
        CHECK (category IS NULL OR category IN ({OLD_CATEGORIES}))
        """
    )
