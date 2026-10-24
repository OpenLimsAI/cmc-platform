"""Append-only scoped QC report previews; these are not approved CoA results."""
from alembic import op

revision = "analytics_qc_preview_20261009"
down_revision = "analytics_qc_point_20261008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT current_database()").scalar() not in (
        "cmc_analytics", "cmc_analytics_training"
    ):
        raise RuntimeError("Expected analytics database")
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(SQL)


def downgrade():
    raise RuntimeError("Retain snapshot evidence; review consumers and rollback first")


SQL = r"""
CREATE SCHEMA IF NOT EXISTS snap_gmp;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE TABLE snap_gmp.qc_report_snapshot (
    snapshot_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_xid bigint NOT NULL DEFAULT txid_current(),
    source_system text NOT NULL,
    source_instance text NOT NULL,
    source_cutoff timestamptz NOT NULL,
    raw_read_at timestamptz NOT NULL,
    template_filename text NOT NULL,
    template_sha256 text NOT NULL CHECK(length(template_sha256)=64),
    rule_version text NOT NULL,
    sample_ids text[] NOT NULL CHECK(cardinality(sample_ids) BETWEEN 1 AND 20),
    manifest jsonb NOT NULL,
    row_count integer NOT NULL CHECK(row_count BETWEEN 1 AND 9999),
    candidate_count integer NOT NULL CHECK(candidate_count>=0),
    validation_status text NOT NULL DEFAULT 'development_preview'
        CHECK(validation_status='development_preview')
);
CREATE TABLE snap_gmp.qc_report_source_row (
    snapshot_id uuid NOT NULL REFERENCES snap_gmp.qc_report_snapshot,
    table_name text NOT NULL,
    row_key_sha256 text NOT NULL CHECK(length(row_key_sha256)=64),
    payload jsonb NOT NULL,
    PRIMARY KEY(snapshot_id,table_name,row_key_sha256)
);
CREATE TABLE staging.qc_report_candidate (
    snapshot_id uuid NOT NULL REFERENCES snap_gmp.qc_report_snapshot,
    candidate_id text NOT NULL,
    sample_id text NOT NULL,
    batch_number text,
    source_batch_id text,
    packet jsonb NOT NULL,
    output jsonb NOT NULL,
    numeric_value numeric,
    numeric_reason text NOT NULL,
    PRIMARY KEY(snapshot_id,candidate_id),
    CHECK(output->>'status' IN ('preview_ready','needs_review'))
);
CREATE INDEX ix_qc_report_candidate_sample ON staging.qc_report_candidate(sample_id);
COMMENT ON TABLE snap_gmp.qc_report_snapshot IS
    'Scoped Mac raw observation, mixed per-table cutoffs; not Oracle SCN or signed report reconstruction';
COMMENT ON TABLE staging.qc_report_candidate IS
    'Strict report candidates and preserved investigation evidence; never approval or release eligibility';

CREATE FUNCTION snap_gmp.qc_preview_same_transaction() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT created_xid FROM snap_gmp.qc_report_snapshot
        WHERE snapshot_id=NEW.snapshot_id) IS DISTINCT FROM txid_current() THEN
        RAISE EXCEPTION 'A committed preview version cannot receive further rows';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION snap_gmp.qc_preview_same_transaction() FROM PUBLIC;
CREATE TRIGGER qc_source_append_guard BEFORE INSERT ON snap_gmp.qc_report_source_row
FOR EACH ROW EXECUTE FUNCTION snap_gmp.qc_preview_same_transaction();
CREATE TRIGGER qc_candidate_append_guard BEFORE INSERT ON staging.qc_report_candidate
FOR EACH ROW EXECUTE FUNCTION snap_gmp.qc_preview_same_transaction();

CREATE VIEW mart.v_qc_report_result_preview AS
SELECT c.snapshot_id,c.candidate_id,c.sample_id,c.batch_number,c.source_batch_id,
       s.source_system,s.source_instance,s.source_cutoff,s.raw_read_at,s.created_at,
       s.template_filename,s.template_sha256,s.rule_version,s.validation_status,
       c.packet->>'spec_id' AS spec_id,c.packet->>'spec_version' AS spec_version,
       c.packet->'original'->'key' AS original_key,
       c.packet->'original'->>'display_value' AS original_display_value,
       c.packet->'original'->>'units' AS original_units,
       c.packet->'report_metadata' AS report_metadata,
       c.packet->'investigations' AS investigations,
       c.output->>'status' AS status,c.output->'reasons' AS reasons,
       c.output->'selected' AS selected,c.packet->'replacements' AS replacements,
       c.packet->'template_exceptions' AS template_exceptions,
       c.numeric_value,c.numeric_reason,
       count(*) OVER (PARTITION BY c.snapshot_id,c.packet->'original'->'key')
          AS specification_candidate_count
FROM staging.qc_report_candidate c JOIN snap_gmp.qc_report_snapshot s USING(snapshot_id);
COMMENT ON VIEW mart.v_qc_report_result_preview IS
    'All versions; consumers MUST select a snapshot_id; preview_ready is not approved-final';

CREATE VIEW mart.v_qc_numeric_result_preview AS
SELECT *, 'numeric_preview_only'::text AS numeric_eligibility
FROM mart.v_qc_report_result_preview
WHERE status='preview_ready' AND numeric_value IS NOT NULL
  AND specification_candidate_count=1;
COMMENT ON VIEW mart.v_qc_numeric_result_preview IS
    'Exact numeric display equals source transformvalue; no censor/text extraction; not validated Cpk/APR';

CREATE VIEW mart.v_qc_investigation_preview AS
SELECT * FROM mart.v_qc_report_result_preview
WHERE jsonb_array_length(investigations)>0 OR jsonb_array_length(replacements)>0;

DO $$ BEGIN
    IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='qc_report_preview_writer') THEN
        CREATE ROLE qc_report_preview_writer NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA snap_gmp,staging TO qc_report_preview_writer;
REVOKE ALL ON snap_gmp.qc_report_snapshot,snap_gmp.qc_report_source_row,
    staging.qc_report_candidate FROM PUBLIC,lims_reader,lims_admin,qc_report_preview_writer;
GRANT SELECT ON snap_gmp.qc_report_snapshot,snap_gmp.qc_report_source_row,
    staging.qc_report_candidate TO qc_report_preview_writer;
GRANT INSERT(snapshot_id,source_system,source_instance,source_cutoff,raw_read_at,
    template_filename,template_sha256,rule_version,sample_ids,manifest,row_count,candidate_count)
    ON snap_gmp.qc_report_snapshot TO qc_report_preview_writer;
GRANT INSERT ON snap_gmp.qc_report_source_row,staging.qc_report_candidate
    TO qc_report_preview_writer;
GRANT USAGE ON SCHEMA mart TO lims_reader;
GRANT SELECT ON mart.v_qc_report_result_preview,mart.v_qc_numeric_result_preview,
    mart.v_qc_investigation_preview TO lims_reader;
"""
