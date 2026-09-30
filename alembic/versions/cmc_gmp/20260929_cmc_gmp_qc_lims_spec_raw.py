"""Add the four LabVantage specification raw mirrors for QC LIMS.

Source fields/PK: qc-lims-etl/schema_meta snapshot; no data change.
The XLSX development snapshot is loaded separately on Mac after this migration.
"""
from __future__ import annotations

from alembic import op

revision = "gmp_qc_spec_raw_20260929"
down_revision = "cmc_gmp_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("""
CREATE TABLE raw_gmp_lims_labvantage.sdispec (
    sdcid text,
    keyid1 text,
    keyid2 text,
    keyid3 text,
    specid text,
    specversionid text,
    decheckflag text,
    condition text,
    waivedflag text,
    usersequence numeric,
    auditsequence numeric,
    createdt timestamptz,
    createby text,
    createtool text,
    moddt timestamptz,
    modby text,
    modtool text,
    tracelogid text,
    activeflag text,
    oosgeneratingflag text NOT NULL,
    autoapplyflag text NOT NULL,
    appliedflag text NOT NULL,
    u_checkflag text,
    u_versionflag text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, specid, specversionid)
);
    """)
    bind.exec_driver_sql("""
CREATE INDEX ix_sdispec_moddt ON raw_gmp_lims_labvantage.sdispec (moddt);
    """)
    bind.exec_driver_sql("""
CREATE TABLE raw_gmp_lims_labvantage.sdidataitemspec (
    sdcid text,
    keyid1 text,
    keyid2 text,
    keyid3 text,
    paramlistid text,
    paramlistversionid text,
    variantid text,
    dataset numeric,
    paramid text,
    paramtype text,
    replicateid numeric,
    specid text,
    specversionid text,
    limittypeid text,
    condition text,
    waivedflag text,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    createdt timestamptz,
    createby text,
    createtool text,
    moddt timestamptz,
    modby text,
    modtool text,
    displayvalue text,
    transformvalue numeric,
    reportflag text,
    checkedvalue numeric,
    checkedtext text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset, paramid, paramtype, replicateid, specid, specversionid)
);
    """)
    bind.exec_driver_sql("""
CREATE INDEX ix_sdidataitemspec_moddt ON raw_gmp_lims_labvantage.sdidataitemspec (moddt);
    """)
    bind.exec_driver_sql("""
CREATE TABLE raw_gmp_lims_labvantage.spec (
    specid text,
    specversionid text,
    specdesc text,
    specoptions text,
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
    versionstatus text,
    ruletypeflag text,
    spectypeflag text,
    activeflag text,
    embeddedflag text,
    defaultcondition text,
    versionapproveddt timestamptz,
    versioneffectivedt timestamptz,
    specuseaddressid text,
    specuseaddresstype text,
    specusetype text,
    oosgeneratingflag text NOT NULL,
    u_inspection text,
    u_expirydt text,
    u_monitorstatus text,
    u_inspection_eng text,
    securityuser text,
    securitydepartment text,
    u_approvalflow text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (specid, specversionid)
);
    """)
    bind.exec_driver_sql("""
CREATE INDEX ix_spec_moddt ON raw_gmp_lims_labvantage.spec (moddt);
    """)
    bind.exec_driver_sql("""
CREATE TABLE raw_gmp_lims_labvantage.specparamitems (
    specid text,
    specversionid text,
    paramlistid text,
    paramlistversionid text,
    variantid text,
    paramid text,
    paramtype text,
    unitsid text,
    allowanyparamlistflag text,
    datatypes text,
    entrysdcid text,
    entryreftypeid text,
    usersequence numeric,
    auditsequence numeric,
    tracelogid text,
    displayformat text,
    reportflag text,
    moddt timestamptz,
    modby text,
    modtool text,
    createdt timestamptz,
    createby text,
    createtool text,
    transformrule text,
    limitlabel text,
    limittyperule text,
    roundingprecision numeric,
    roundingfunction text,
    u_reportname text,
    u_limitlabel_eng text,
    _lims_extracted_at timestamptz,
    _etl_loaded_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (specid, specversionid, paramlistid, paramlistversionid, variantid, paramid, paramtype)
);
    """)
    bind.exec_driver_sql("""
CREATE INDEX ix_specparamitems_moddt ON raw_gmp_lims_labvantage.specparamitems (moddt);
    """)
    bind.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON raw_gmp_lims_labvantage.sdispec TO gmp_etl")
    bind.exec_driver_sql("GRANT SELECT ON raw_gmp_lims_labvantage.sdispec TO gmp_reader")
    bind.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON raw_gmp_lims_labvantage.sdidataitemspec TO gmp_etl")
    bind.exec_driver_sql("GRANT SELECT ON raw_gmp_lims_labvantage.sdidataitemspec TO gmp_reader")
    bind.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON raw_gmp_lims_labvantage.spec TO gmp_etl")
    bind.exec_driver_sql("GRANT SELECT ON raw_gmp_lims_labvantage.spec TO gmp_reader")
    bind.exec_driver_sql("GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON raw_gmp_lims_labvantage.specparamitems TO gmp_etl")
    bind.exec_driver_sql("GRANT SELECT ON raw_gmp_lims_labvantage.specparamitems TO gmp_reader")


def downgrade() -> None:
    raise NotImplementedError("Raw specification data may exist; restore through a reviewed backup/release plan")
