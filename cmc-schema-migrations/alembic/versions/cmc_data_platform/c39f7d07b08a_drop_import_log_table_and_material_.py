"""drop import_log table and material.import_batch_id (remove material import feature)

Revision ID: c39f7d07b08a
Revises: 546734e2d5e6
Create Date: 2026-06-10 00:54:51.425247
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'c39f7d07b08a'
down_revision = '546734e2d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 移除"物料 Excel 导入"功能:先丢 material 上的 FK 列,再丢 import_log 表
    op.drop_column("material", "import_batch_id", schema="material_mgmt")
    op.execute("DROP TABLE IF EXISTS material_mgmt.import_log")


def downgrade() -> None:
    # 重建 import_log 表 + material.import_batch_id FK 列(回到 546734e2d5e6 形态)
    op.execute("""
        CREATE TABLE material_mgmt.import_log (
            import_id     integer NOT NULL,
            file_name     character varying(200),
            imported_at   timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
            operator      character varying(50),
            total_rows    integer DEFAULT 0,
            inserted_rows integer DEFAULT 0,
            updated_rows  integer DEFAULT 0,
            failed_rows   integer DEFAULT 0,
            error_detail  jsonb
        );
    """)
    op.execute("""
        CREATE SEQUENCE material_mgmt.import_log_import_id_seq
            AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
    """)
    op.execute("ALTER SEQUENCE material_mgmt.import_log_import_id_seq OWNED BY material_mgmt.import_log.import_id;")
    op.execute("ALTER TABLE ONLY material_mgmt.import_log ALTER COLUMN import_id SET DEFAULT nextval('material_mgmt.import_log_import_id_seq'::regclass);")
    op.execute("ALTER TABLE ONLY material_mgmt.import_log ADD CONSTRAINT import_log_pkey PRIMARY KEY (import_id);")
    op.add_column("material", sa.Column("import_batch_id", sa.Integer(), nullable=True),
                  schema="material_mgmt")
    op.execute("""
        ALTER TABLE ONLY material_mgmt.material
            ADD CONSTRAINT material_import_batch_id_fkey
            FOREIGN KEY (import_batch_id)
            REFERENCES material_mgmt.import_log(import_id) ON DELETE SET NULL;
    """)
