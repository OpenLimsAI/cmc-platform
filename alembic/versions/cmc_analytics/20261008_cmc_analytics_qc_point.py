"""Add current source water point labels without changing result identities."""
from alembic import op
revision = "analytics_qc_point_20261008"
down_revision = "cmc_analytics_qc_lv_water_v1"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
ALTER TABLE staging.stg_lv_sample ADD COLUMN samplepoint_code text, ADD COLUMN samplepoint_name text, ADD COLUMN samplepoint_mapping_source text, ADD COLUMN samplepoint_mapping_scope text, ADD COLUMN samplepoint_source_moddt timestamptz, ADD COLUMN samplepoint_extracted_at timestamptz;
COMMENT ON COLUMN staging.stg_lv_sample.samplepoint_mapping_scope IS 'current_master: observed master mapping, not sampling-time historical identity';
ALTER TABLE staging.stg_lv_test_result_wide ADD COLUMN samplepoint_code text, ADD COLUMN samplepoint_name text, ADD COLUMN samplepoint_mapping_source text, ADD COLUMN samplepoint_mapping_scope text, ADD COLUMN samplepoint_source_moddt timestamptz, ADD COLUMN samplepoint_extracted_at timestamptz;
COMMENT ON COLUMN staging.stg_lv_test_result_wide.samplepoint_mapping_scope IS 'current_master: observed master mapping, not sampling-time historical identity';
CREATE INDEX ix_stg_lv_trw_point_code ON staging.stg_lv_test_result_wide(source_system, samplepoint_code);
    """)

def downgrade():
    raise RuntimeError("Consumers and captured mapping must be reviewed before removal")
