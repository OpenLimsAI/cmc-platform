"""Describe the retained current mirror after local history retirement."""
from alembic import context, op

revision = "gmp_qc_point_note_20261008"
down_revision = "gmp_qc_point_nohist_20261008"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Water-point comment requires the verified online target")
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT current_database()").scalar() != "cmc_gmp":
        raise RuntimeError("Expected cmc_gmp")
    if bind.exec_driver_sql(
        "SELECT to_regclass('raw_gmp_lims_labvantage.s_samplepoint_history')"
    ).scalar() is not None:
        raise RuntimeError("Apply the reviewed history-removal revision first")
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("COMMENT ON TABLE raw_gmp_lims_labvantage.s_samplepoint IS "
               "'MBTK.S_SAMPLEPOINT current mirror; local history retired on 2026-10-08; mapping is not sampling-time historical identity'")


def downgrade():
    op.execute("COMMENT ON TABLE raw_gmp_lims_labvantage.s_samplepoint IS "
               "'MBTK.S_SAMPLEPOINT current mirror; history starts with first capture, not historical effective dates'")
