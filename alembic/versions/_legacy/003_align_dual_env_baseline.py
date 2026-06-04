"""align Mac/Linux baseline — record the manual reconciliation done 2026-05-13

Revision ID: 003
Revises: 002
Create Date: 2026-05-13

Background:
    Before this revision the two cmc_data_platform instances (Mac dev / Linux deploy)
    had drifted apart over time, exhibiting 116 structural differences (3 schemas
    out of sync, 21 tables only on one side, type/column differences in meta).

    On 2026-05-13 the two were reconciled manually. This migration is a *recipe*
    that reproduces the same final state on a fresh database, so future deploys
    (or disaster-recovery rebuilds) can reach the post-reconciliation state by
    running `alembic upgrade head` from scratch.

    Already-aligned databases are stamped to this revision directly via
    `alembic stamp head` and never run this code.

Changes captured:
    1. material_mgmt: add app_user / audit_log / auth_session tables (auth & audit)
    2. raw_qc_lims:  new schema for raw LIMS data (batch / result / sample)
    3. cost_accounting: new schema for BOM-based cost accounting
                       (5 tables + 3 views + 1 function + 5 sequences + 15 indexes + 3 triggers)
    4. meta.dim_employee: add group_id (nullable text), add status (NOT NULL default 'active'),
                          tighten department (NOT NULL default '药学及技术转移部')
"""
from __future__ import annotations

from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "003"


def _run_sql_file(filename: str) -> None:
    """Execute a multi-statement SQL file via the raw driver.

    Uses exec_driver_sql instead of op.execute so that:
      - multi-statement SQL goes through as one psycopg2 call,
      - any '%' in COMMENT bodies isn't mistaken for a parameter placeholder.
    """
    path = ASSETS_DIR / filename
    sql = path.read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    # 1. New auth/audit tables under material_mgmt
    _run_sql_file("01_material_mgmt_auth_tables.sql")

    # 2. New raw_qc_lims schema (LIMS raw layer)
    _run_sql_file("02_raw_qc_lims_schema.sql")

    # 3. New cost_accounting schema
    _run_sql_file("03_cost_accounting_schema.sql")

    # 4. meta.dim_employee column additions + constraint tightening
    op.add_column(
        "dim_employee",
        sa.Column("group_id", sa.Text(), nullable=True),
        schema="meta",
    )
    op.add_column(
        "dim_employee",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        schema="meta",
    )
    # Backfill any NULL department before tightening NOT NULL on it
    op.execute(
        "UPDATE meta.dim_employee "
        "SET department = '药学及技术转移部' "
        "WHERE department IS NULL"
    )
    op.alter_column(
        "dim_employee",
        "department",
        nullable=False,
        server_default=sa.text("'药学及技术转移部'"),
        schema="meta",
    )


def downgrade() -> None:
    # Reverse meta.dim_employee changes
    op.alter_column(
        "dim_employee",
        "department",
        nullable=True,
        server_default=None,
        schema="meta",
    )
    op.drop_column("dim_employee", "status", schema="meta")
    op.drop_column("dim_employee", "group_id", schema="meta")

    # Drop schemas / tables introduced in upgrade
    op.execute("DROP SCHEMA IF EXISTS cost_accounting CASCADE")
    op.execute("DROP SCHEMA IF EXISTS raw_qc_lims CASCADE")
    op.execute("DROP TABLE IF EXISTS material_mgmt.auth_session CASCADE")
    op.execute("DROP TABLE IF EXISTS material_mgmt.audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS material_mgmt.app_user CASCADE")
