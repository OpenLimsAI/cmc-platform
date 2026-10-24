"""Allow QC runtime log INSERTs to obtain their existing sequence IDs."""
from alembic import context, op

revision = "gmp_qc_meta_seq_20261008"
down_revision = "gmp_etl_password_20261008"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("QC sequence grants require verified online objects")
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT current_database()").scalar() != "cmc_gmp":
        raise RuntimeError("Expected cmc_gmp")
    # Only these two owned sequences are used by the QC state writer.
    for table, column, sequence in (
        ("meta.etl_run", "run_id", "meta.etl_run_run_id_seq"),
        ("meta.load_error_log", "error_id", "meta.load_error_log_error_id_seq"),
    ):
        actual = bind.exec_driver_sql(
            "SELECT pg_get_serial_sequence(%s,%s)", (table, column)
        ).scalar()
        if actual != sequence:
            raise RuntimeError("QC meta sequence ownership differs from the reviewed objects")
    op.execute(
        "GRANT USAGE ON SEQUENCE meta.etl_run_run_id_seq, "
        "meta.load_error_log_error_id_seq TO gmp_etl"
    )


def downgrade():
    raise RuntimeError("Review active QC clients and prior sequence ACLs before revoking runtime grants")
