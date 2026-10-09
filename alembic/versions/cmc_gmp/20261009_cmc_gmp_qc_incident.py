"""Add verified incident mirrors and a scoped snapshot reader; no Oracle SQL."""
from alembic import op
revision = "gmp_qc_incident_20261009"
down_revision = "gmp_qc_point_note_20261008"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT current_database()").scalar() != "cmc_gmp":
        raise RuntimeError("Expected cmc_gmp")
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.execute(SQL)

def downgrade():
    raise RuntimeError("Retain snapshots/raw evidence; use a reviewed rollback plan")

SQL = r"""
CREATE TABLE raw_gmp_lims_labvantage.incident (
    incidentid text,
    incidentdesc text,
    incidenttype text,
    incidentstatus text,
    incidentdt timestamptz,
    incidentduedt timestamptz,
    incidentcategory text,
    standardreference text,
    reportedby text,
    explanation text,
    rootcause text,
    roottrigger text,
    triage text,
    riskdone text,
    risknotdone text,
    severity text,
    departmentid text,
    locationid text,
    capareqflag text,
    woreqflag text,
    investigationreqflag text,
    incidentauditreference text,
    incidentauditby text,
    incidentauditdt timestamptz,
    expirationevent text,
    expirationdt timestamptz,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    templateflag text,
    createdt timestamptz,
    createby text,
    createtool text,
    moddt timestamptz,
    modby text,
    modtool text,
    activeflag text,
    u_begindate timestamptz,
    u_enddate timestamptz,
    u_treatment text,
    u_capaid text,
    u_incdtsource text,
    u_oosid text,
    u_reportapprovestatus text,
    u_reportrequiredflag text,
    u_trackresult text,
    u_assessment text,
    u_oosreview text,
    u_closedt timestamptz,
    u_incdtmanager text,
    u_approveflowid text,
    securityuser text,
    securitydepartment text,
    u_approvalid text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (incidentid)
);
CREATE INDEX ix_incident_moddt ON raw_gmp_lims_labvantage.incident (moddt);
CREATE TABLE raw_gmp_lims_labvantage.incidentitem (
    incidentitemid text,
    incidentid text,
    incidentitemdesc text,
    sourcesdcid text,
    sourcekeyid1 text,
    sourcekeyid2 text,
    sourcekeyid3 text,
    paramlistid text,
    paramlistversionid text,
    variantid text,
    dataset numeric,
    paramid text,
    paramtype text,
    replicateid numeric,
    usersequence numeric,
    auditsequence numeric,
    causalobjectflag text,
    moddt timestamptz,
    modby text,
    modtool text,
    tracelogid text,
    createdt timestamptz,
    createby text,
    createtool text,
    u_sdiworkitemid text,
    u_workitemversionid text,
    u_workiteminstance numeric,
    u_workitemid text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (incidentid, incidentitemid)
);
CREATE INDEX ix_incidentitem_moddt ON raw_gmp_lims_labvantage.incidentitem (moddt);
CREATE INDEX ix_s_sample_parent ON raw_gmp_lims_labvantage.s_sample(u_parentsampleid);
CREATE INDEX ix_incidentitem_source ON raw_gmp_lims_labvantage.incidentitem(sourcesdcid,sourcekeyid1);
CREATE INDEX ix_sdidataitemspec_sample ON raw_gmp_lims_labvantage.sdidataitemspec(sdcid,keyid1);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='gmp_qc_snapshot_reader') THEN CREATE ROLE gmp_qc_snapshot_reader NOLOGIN; END IF; END $$;
GRANT USAGE ON SCHEMA raw_gmp_lims_labvantage,meta TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.s_sample TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.s_batch TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.sdidata TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.sdidataitem TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.sdidataitemspec TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.spec TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.specparamitems TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.paramlist TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.incident TO gmp_qc_snapshot_reader;
GRANT SELECT ON raw_gmp_lims_labvantage.incidentitem TO gmp_qc_snapshot_reader;
GRANT SELECT,INSERT,UPDATE ON raw_gmp_lims_labvantage.incident TO gmp_etl;
GRANT SELECT ON raw_gmp_lims_labvantage.incident TO gmp_reader;
GRANT SELECT,INSERT,UPDATE ON raw_gmp_lims_labvantage.incidentitem TO gmp_etl;
GRANT SELECT ON raw_gmp_lims_labvantage.incidentitem TO gmp_reader;
GRANT SELECT ON meta.etl_run,meta.etl_watermark TO gmp_qc_snapshot_reader;
COMMENT ON TABLE raw_gmp_lims_labvantage.incident IS 'MBTK.INCIDENT current mirror; source schema read-only verified 2026-10-09; adoption status is not approval evidence';
COMMENT ON TABLE raw_gmp_lims_labvantage.incidentitem IS 'MBTK.INCIDENTITEM complete current mirror; source linkage preserves parameter constraints';
"""
