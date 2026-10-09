"""Expose snapshot scope and zero-candidate coverage to read-only consumers."""
from alembic import op

revision = "analytics_qc_catalog_20261009"
down_revision = "analytics_qc_null_20261009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("""
CREATE VIEW mart.v_qc_report_snapshot_preview AS
SELECT snapshot_id,created_at,source_system,source_instance,source_cutoff,
       raw_read_at,template_filename,template_sha256,rule_version,sample_ids,
       row_count,candidate_count,validation_status,manifest
FROM snap_gmp.qc_report_snapshot;
COMMENT ON VIEW mart.v_qc_report_snapshot_preview IS
    'Version catalogue, scoped sample coverage and mixed-table cutoff manifest; choose an explicit snapshot_id';
GRANT SELECT ON mart.v_qc_report_snapshot_preview TO lims_reader;
    """)


def downgrade():
    raise RuntimeError("Review snapshot catalogue consumers before removing access")
