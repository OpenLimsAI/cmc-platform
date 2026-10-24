"""Capture formal LabVantage water point master with append-only change history."""
from alembic import op
revision = "gmp_qc_point_raw_20261008"
down_revision = "gmp_qc_stg_link_idx_20260929"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
CREATE TABLE raw_gmp_lims_labvantage.s_samplepoint (
    s_samplepointid text,
    samplepointdesc text,
    createdt timestamptz,
    createby text,
    createtool text,
    moddt timestamptz,
    modby text,
    modtool text,
    notes text,
    auditsequence numeric,
    tracelogid text,
    productid text,
    templateflag text,
    usersequence numeric,
    activeflag text,
    locationid text,
    productversionid text,
    excursionflag text,
    locationlabel text,
    instancecount numeric,
    latitude text,
    longitude text,
    projection text,
    maxactivitysize numeric,
    createactivityrule text,
    testingdepartmentid text,
    workareadepartmentid text,
    autoassignrule text,
    autoassignanalystid text,
    sitedepartmentid text,
    u_locationid text,
    u_mincollectnum numeric,
    u_mincollectunit text,
    u_locationlevel text,
    u_roomarea text,
    u_samplepointtype text,
    u_sampletemplateid text,
    securityuser text,
    securitydepartment text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (s_samplepointid)
);
CREATE INDEX ix_s_samplepoint_moddt ON raw_gmp_lims_labvantage.s_samplepoint (moddt);

CREATE TABLE raw_gmp_lims_labvantage.s_samplepoint_history (
    history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    s_samplepointid text NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    operation text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_record jsonb,
    new_record jsonb
);
CREATE INDEX ix_s_samplepoint_history_id ON raw_gmp_lims_labvantage.s_samplepoint_history(s_samplepointid, observed_at);
CREATE FUNCTION raw_gmp_lims_labvantage.record_samplepoint_history() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    INSERT INTO raw_gmp_lims_labvantage.s_samplepoint_history(s_samplepointid, operation, old_record, new_record)
    VALUES (COALESCE(NEW.s_samplepointid, OLD.s_samplepointid), TG_OP,
            CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
            CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END);
    RETURN NULL;
END $$;
CREATE TRIGGER samplepoint_history AFTER INSERT OR UPDATE OR DELETE
ON raw_gmp_lims_labvantage.s_samplepoint FOR EACH ROW
EXECUTE FUNCTION raw_gmp_lims_labvantage.record_samplepoint_history();
CREATE FUNCTION raw_gmp_lims_labvantage.reject_samplepoint_history_change() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Water point history is append only'; END $$;
CREATE TRIGGER samplepoint_history_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
ON raw_gmp_lims_labvantage.s_samplepoint_history FOR EACH STATEMENT
EXECUTE FUNCTION raw_gmp_lims_labvantage.reject_samplepoint_history_change();
REVOKE ALL ON FUNCTION raw_gmp_lims_labvantage.record_samplepoint_history() FROM PUBLIC;
COMMENT ON TABLE raw_gmp_lims_labvantage.s_samplepoint IS 'MBTK.S_SAMPLEPOINT current mirror; history starts with first capture, not historical effective dates';

DO $$ DECLARE a record; role_sql text; BEGIN
 FOR a IN SELECT grantee, privilege_type FROM information_schema.role_table_grants
 WHERE table_schema='raw_gmp_lims_labvantage' AND table_name='s_sample' AND privilege_type IN ('SELECT','INSERT','UPDATE') LOOP
  role_sql := CASE WHEN a.grantee='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(a.grantee) END;
  EXECUTE 'GRANT ' || a.privilege_type || ' ON raw_gmp_lims_labvantage.s_samplepoint TO ' || role_sql;
  IF a.privilege_type='SELECT' THEN
   EXECUTE 'GRANT SELECT ON raw_gmp_lims_labvantage.s_samplepoint_history TO ' || role_sql;
  END IF;
 END LOOP;
END $$;

    """)

def downgrade():
    raise RuntimeError("Point master and history require reviewed backup and rollback; no automatic removal")
