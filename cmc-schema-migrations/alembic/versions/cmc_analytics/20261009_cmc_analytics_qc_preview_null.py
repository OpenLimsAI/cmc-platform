"""Expose blocked selections as SQL NULL, preserving the original JSON evidence."""
from alembic import op
revision = "analytics_qc_null_20261009"
down_revision = "analytics_qc_preview_20261009"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(SQL)

def downgrade():
    raise RuntimeError("Retain the explicit NULL contract for consumers")

SQL = "CREATE OR REPLACE VIEW mart.v_qc_report_result_preview AS\nSELECT c.snapshot_id,c.candidate_id,c.sample_id,c.batch_number,c.source_batch_id,\n       s.source_system,s.source_instance,s.source_cutoff,s.raw_read_at,s.created_at,\n       s.template_filename,s.template_sha256,s.rule_version,s.validation_status,\n       c.packet->>'spec_id' AS spec_id,c.packet->>'spec_version' AS spec_version,\n       c.packet->'original'->'key' AS original_key,\n       c.packet->'original'->>'display_value' AS original_display_value,\n       c.packet->'original'->>'units' AS original_units,\n       c.packet->'report_metadata' AS report_metadata,\n       c.packet->'investigations' AS investigations,\n       c.output->>'status' AS status,c.output->'reasons' AS reasons,\n       NULLIF(c.output->'selected','null'::jsonb) AS selected,c.packet->'replacements' AS replacements,\n       c.packet->'template_exceptions' AS template_exceptions,\n       c.numeric_value,c.numeric_reason,\n       count(*) OVER (PARTITION BY c.snapshot_id,c.packet->'original'->'key')\n          AS specification_candidate_count\nFROM staging.qc_report_candidate c JOIN snap_gmp.qc_report_snapshot s USING(snapshot_id);\n"
