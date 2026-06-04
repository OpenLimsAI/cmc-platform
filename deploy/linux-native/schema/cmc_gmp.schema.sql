--
-- PostgreSQL database dump
--

\restrict ngZofU87oV5VMqCINh2EBuXl8Sz2kdqNZh3ph4IxrocaTprCb7xgqeJzuboAvTI

-- Dumped from database version 16.13 (Debian 16.13-1.pgdg13+1)
-- Dumped by pg_dump version 16.13 (Debian 16.13-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: meta; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA meta;


--
-- Name: SCHEMA meta; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA meta IS 'ETL 治理、审计、设备本地缓存。cmc_rd 与 cmc_gmp 此 schema 内表结构完全一致（标准 meta 集）。';


--
-- Name: raw_gmp_lims_labvantage; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_gmp_lims_labvantage;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_audit_log; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.access_audit_log (
    access_id bigint NOT NULL,
    access_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_name text,
    client_addr inet,
    session_id text,
    access_type text,
    query_text text,
    target_objects jsonb,
    rows_returned bigint
);


--
-- Name: TABLE access_audit_log; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.access_audit_log IS '查询访问审计，FDA / EMA 检查必备。Phase 0 即启用，避免补历史。';


--
-- Name: COLUMN access_audit_log.access_type; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON COLUMN meta.access_audit_log.access_type IS 'QUERY / EXPORT / API / ETL_READ';


--
-- Name: access_audit_log_access_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

CREATE SEQUENCE meta.access_audit_log_access_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: access_audit_log_access_id_seq; Type: SEQUENCE OWNED BY; Schema: meta; Owner: -
--

ALTER SEQUENCE meta.access_audit_log_access_id_seq OWNED BY meta.access_audit_log.access_id;


--
-- Name: data_correction_log; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.data_correction_log (
    correction_id bigint NOT NULL,
    corrected_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    corrected_by text,
    target_schema text NOT NULL,
    target_table text NOT NULL,
    target_pk jsonb,
    operation text NOT NULL,
    before_values jsonb,
    after_values jsonb,
    reason text,
    approved_by text,
    approved_at timestamp without time zone
);


--
-- Name: TABLE data_correction_log; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.data_correction_log IS 'raw 层数据修正审计。raw 表 append-only，任何 update/delete 必须在此留痕。';


--
-- Name: COLUMN data_correction_log.operation; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON COLUMN meta.data_correction_log.operation IS 'UPDATE / DELETE / INSERT';


--
-- Name: data_correction_log_correction_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

CREATE SEQUENCE meta.data_correction_log_correction_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: data_correction_log_correction_id_seq; Type: SEQUENCE OWNED BY; Schema: meta; Owner: -
--

ALTER SEQUENCE meta.data_correction_log_correction_id_seq OWNED BY meta.data_correction_log.correction_id;


--
-- Name: equipment_lookup; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.equipment_lookup (
    equipment_id text NOT NULL,
    source_instance text NOT NULL,
    line_code text,
    stage text,
    vendor_key text,
    equipment_model text,
    working_volume_l double precision,
    commission_date date,
    valid_from date,
    valid_to date,
    is_active boolean DEFAULT true NOT NULL,
    last_synced_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE equipment_lookup; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.equipment_lookup IS 'cmc_mdm.mdm_core.equipment_master 的本地只读快照，便于库内 join。每日同步。';


--
-- Name: etl_job; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.etl_job (
    job_name text NOT NULL,
    source_system text NOT NULL,
    target_database text NOT NULL,
    target_schema text NOT NULL,
    description text,
    owner text,
    schedule_cron text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE etl_job; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.etl_job IS 'ETL 任务定义：任务名、源系统、目标 schema、责任人、调度、是否启用。';


--
-- Name: etl_run; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.etl_run (
    run_id bigint NOT NULL,
    job_name text NOT NULL,
    source_instance text,
    mode text,
    window_from timestamp without time zone,
    window_to timestamp without time zone,
    run_started_at timestamp without time zone NOT NULL,
    run_finished_at timestamp without time zone,
    status text NOT NULL,
    rows_read bigint DEFAULT 0,
    rows_written bigint DEFAULT 0,
    rows_errored bigint DEFAULT 0,
    message text,
    extra jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE etl_run; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.etl_run IS '每次 ETL 运行的完整记录：模式、窗口、起止、状态、行数、错误数、消息。';


--
-- Name: COLUMN etl_run.mode; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON COLUMN meta.etl_run.mode IS 'procid / manual_window / initial_window / watermark_incremental / full_refresh';


--
-- Name: COLUMN etl_run.status; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON COLUMN meta.etl_run.status IS 'RUNNING / SUCCESS / FAILED / PARTIAL_FAILED';


--
-- Name: etl_run_run_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

CREATE SEQUENCE meta.etl_run_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etl_run_run_id_seq; Type: SEQUENCE OWNED BY; Schema: meta; Owner: -
--

ALTER SEQUENCE meta.etl_run_run_id_seq OWNED BY meta.etl_run.run_id;


--
-- Name: etl_watermark; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.etl_watermark (
    job_name text NOT NULL,
    source_system text NOT NULL,
    source_instance text DEFAULT ''::text NOT NULL,
    target_table text NOT NULL,
    last_success_ts timestamp without time zone,
    last_run_id bigint,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE etl_watermark; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.etl_watermark IS '每个 (job, 源系统, 源实例, 目标表) 的增量水位。仅存上次成功同步到的时间点，运行明细见 etl_run。';


--
-- Name: load_error_log; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.load_error_log (
    error_id bigint NOT NULL,
    run_id bigint,
    error_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    source_system text,
    source_instance text,
    target_schema text,
    target_table text,
    error_type text,
    error_message text,
    context jsonb,
    offending_data jsonb
);


--
-- Name: TABLE load_error_log; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.load_error_log IS 'ETL 失败行的详情。每次失败一行，便于复盘。';


--
-- Name: COLUMN load_error_log.error_type; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON COLUMN meta.load_error_log.error_type IS 'PARSE / VALIDATION / SQL / CONNECTION / OTHER';


--
-- Name: load_error_log_error_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

CREATE SEQUENCE meta.load_error_log_error_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: load_error_log_error_id_seq; Type: SEQUENCE OWNED BY; Schema: meta; Owner: -
--

ALTER SEQUENCE meta.load_error_log_error_id_seq OWNED BY meta.load_error_log.error_id;


--
-- Name: source_file_registry; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.source_file_registry (
    file_id bigint NOT NULL,
    source_system text NOT NULL,
    source_instance text,
    file_path text NOT NULL,
    file_hash text,
    file_size_bytes bigint,
    row_count bigint,
    loaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    loaded_by_run_id bigint,
    status text DEFAULT 'LOADED'::text NOT NULL
);


--
-- Name: TABLE source_file_registry; Type: COMMENT; Schema: meta; Owner: -
--

COMMENT ON TABLE meta.source_file_registry IS '文件型数据源的接入登记，防止重复加载。Lucullus（DB 直读）不写此表。';


--
-- Name: source_file_registry_file_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

CREATE SEQUENCE meta.source_file_registry_file_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_file_registry_file_id_seq; Type: SEQUENCE OWNED BY; Schema: meta; Owner: -
--

ALTER SEQUENCE meta.source_file_registry_file_id_seq OWNED BY meta.source_file_registry.file_id;


--
-- Name: param; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.param (
    paramid text NOT NULL,
    paramdesc text,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    templateflag text,
    modtool text,
    activeflag text,
    securityuser text,
    securitydepartment text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: paramlist; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.paramlist (
    paramlistid text NOT NULL,
    paramlistversionid text NOT NULL,
    variantid text NOT NULL,
    limitruleid text,
    limitruleversionid text,
    approvaltypeid text,
    paramlistdesc text,
    modifiableflag text NOT NULL,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    templateflag text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    modtool text,
    versionstatus text,
    s_paramlisttype text,
    s_trainingreqflag text,
    s_overrideallowedflag text,
    s_instrumenttype text,
    s_cancellableflag text,
    createworksheetrule text,
    s_instrumentmodel text,
    activeflag text,
    s_defaultusagetime numeric,
    versionapproveddt timestamp with time zone,
    versioneffectivedt timestamp with time zone,
    displayunderparamlistname text,
    displayundervariantname text,
    accreditedflag text,
    accrediteddt timestamp with time zone,
    accreditedaddressid text,
    accreditedaddresstype text,
    maxactivitysize numeric,
    createactivityrule text,
    testingdepartmentid text,
    workareadepartmentid text,
    autoassignanalystid text,
    autoassignrule text,
    testinglabtype text,
    workareatype text,
    u_reportgroupid text,
    securityset text,
    u_pltype text,
    u_trainingreqflag text,
    u_paramlist_eng text,
    u_reportgroup_eng text,
    u_empowerdatasetflag text,
    securityuser text,
    securitydepartment text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: paramlistitem; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.paramlistitem (
    paramlistid text NOT NULL,
    paramlistversionid text NOT NULL,
    variantid text NOT NULL,
    paramid text NOT NULL,
    paramtype text NOT NULL,
    aliasid text,
    numreplicates numeric,
    mandatoryflag text,
    displayunits text,
    datatypes text,
    defaultvalue text,
    displayformat text,
    operatorrule text,
    transformrule text,
    entrysdcid text,
    entryreftypeid text,
    calcrule text,
    measurementactionid text,
    usersequence numeric,
    auditsequence numeric,
    tracelogid text,
    transformdeferflag text,
    editstyleflag text,
    weblookupurl text,
    extendedsql text,
    moddt timestamp with time zone,
    modby text,
    modtool text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    instrumentfieldid text,
    managedflag text,
    displaywidth numeric,
    calcruleeditableflag text,
    uncertaintyfunction text,
    uncertaintydisplayformat text,
    uncertaintymanagedflag text,
    uncertaintyasymmetricflag text,
    uncertaintyfunctionupper text,
    uncertaintydisplayformatupper text,
    displayunderparamname text,
    displayunderparamtype text,
    mappingparamid text,
    mappingparamtype text,
    reportflag text,
    qctransferflag text,
    editorstyleid text,
    u_statisticflag text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: s_batch; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.s_batch (
    s_batchid text NOT NULL,
    batchdesc text,
    createdt timestamp with time zone,
    batchdt timestamp with time zone,
    createby text,
    batchstatus text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    modtool text,
    notes text,
    auditsequence numeric,
    tracelogid text,
    usersequence numeric,
    templateflag text,
    productid text,
    releasedby text,
    batchtype text,
    batchsize numeric,
    batchsizeunits text,
    receiveddt timestamp with time zone,
    receivedby text,
    releaseddt timestamp with time zone,
    supplieraddressid text,
    manufacturedt timestamp with time zone,
    supplieraddresstype text,
    prodvariantlotreference text,
    manufactureraddressid text,
    manufactureraddresstype text,
    levelid text,
    disposition text,
    prodvariantid text,
    productionsiteaddressid text,
    productionsiteaddresstype text,
    samplingplanid text,
    samplingplanversionid text,
    activeflag text,
    batchmode text,
    cancelleddt timestamp with time zone,
    productversionid text,
    cancelledby text,
    expectedbatchsize numeric,
    expectedbatchsizeunits text,
    holddt timestamp with time zone,
    holdby text,
    expirydt timestamp with time zone,
    materialid text,
    sitedepartmentid text,
    securityuser text,
    securitydepartment text,
    u_pendingreleaseflag text,
    u_apprstatus text,
    u_approvalopinion text,
    u_apprflag text,
    u_progress text,
    u_approveflag text,
    u_sampletype text,
    u_expirydt timestamp with time zone,
    u_retestdt timestamp with time zone,
    u_supplierbatchno text,
    u_testprocess text,
    u_testitems text,
    u_matregular text,
    u_batchno text,
    u_arrivedate timestamp with time zone,
    u_packageamount text,
    u_packageamount_unit text,
    u_loginby text,
    u_logindate timestamp with time zone,
    u_productcode text,
    u_packageregular text,
    u_logindepartment text,
    u_loginrejectflag text,
    u_regular text,
    u_thflag text,
    u_codeno text,
    u_packagetype text,
    u_checkdeparment text,
    u_packagsize text,
    u_incomingdate timestamp with time zone,
    u_rejectflag text,
    u_skipflag text,
    u_autoreleaseflag text,
    u_batchverifyflag text,
    u_autoreviewflag text,
    u_finishedamount text,
    u_finishedamount_unit text,
    u_prodvariantname text,
    u_acceptby text,
    u_acceptdt timestamp with time zone,
    u_reportby text,
    u_reportdt timestamp with time zone,
    u_numberofpallets numeric,
    u_numberofcontainers numeric,
    u_sapprocessorder text,
    u_sappurchaseorder text,
    u_sapinspectiontype text,
    u_sapoperationnumber text,
    u_sapinspectionlot text,
    u_sapinsplotcreateddt timestamp with time zone,
    u_sapbatchnumber text,
    u_sapmanufname text,
    u_sapmanufnumber text,
    u_sapvendorname text,
    u_sapvendornumber text,
    u_sapvendorbatchnumber text,
    u_sapplant text,
    u_sapworkcenter text,
    u_riskgroup text,
    u_containertypeid text,
    u_sapdispositioncode text,
    u_batchnumberconsumed1 text,
    u_productcodeconsumed1 text,
    u_batchnumberconsumed2 text,
    u_productcodeconsumed2 text,
    u_batchnumberconsumed3 text,
    u_productcodeconsumed3 text,
    u_deliverytype text,
    u_reasonfordelivery text,
    u_harvestnb text,
    u_molecule text,
    u_facility text,
    u_processstep text,
    u_processstepnumber text,
    u_sapreleasetext text,
    u_inhousebatchno text,
    u_testpurpose text,
    u_loginappflow text,
    u_batchappflow text,
    u_projectno text,
    u_duedt timestamp with time zone,
    u_sampleamount numeric,
    u_storagecondition text,
    u_priority text,
    u_expireperiod numeric,
    u_expiryfirstuseperiodunits text,
    u_expireperiodflag text,
    u_updatethebatchflag text,
    u_destroyflag text,
    u_planid text,
    u_planversionid text,
    u_samplename text,
    u_condition text,
    u_reportid text,
    u_productdesc text,
    u_inspection text,
    u_associatedprojectcode text,
    u_aognum text,
    u_receivebathcid text,
    u_samplecode text,
    u_productdepartment text,
    u_returnreason text,
    u_aognumunit text,
    u_approvalflowid text,
    u_prebatchinfofornewid text,
    u_materialexpirydt timestamp with time zone,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: s_sample; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.s_sample (
    s_sampleid text NOT NULL,
    sampledesc text,
    sampletypeid text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    submitterid text,
    modtool text,
    submitteddt timestamp with time zone,
    notes text,
    auditsequence numeric,
    tracelogid text,
    usersequence numeric,
    priority text,
    reviewrequiredflag text,
    disposalstatus text,
    samplestatus text,
    collectiondt timestamp with time zone,
    receiveddt timestamp with time zone,
    batchid text,
    physicalcondition text,
    productid text,
    projectid text,
    samplepointid text,
    locationid text,
    requestid text,
    starttestingdt timestamp with time zone,
    completedt timestamp with time zone,
    disposaldt timestamp with time zone,
    duedt timestamp with time zone,
    basedonsampleid text,
    collectedby text,
    templateflag text,
    receivedby text,
    disposedby text,
    reviewedby text,
    revieweddt timestamp with time zone,
    reviewdisposition text,
    reviewremarks text,
    numberlabels numeric,
    controlsubstanceflag text,
    receiverequiredflag text,
    cocrequiredflag text,
    autoreceiveflag text,
    eventdt timestamp with time zone,
    autofinalrptflag text,
    eventplan text,
    studyid text,
    conditionlabel text,
    eventplanitem text,
    samplefamilyid text,
    schedulerulelabel text,
    confirmedby text,
    confirmeddt timestamp with time zone,
    sstudyid text,
    pooledflag text,
    glpflag text,
    cocflag text,
    restrictionsflag text,
    concentration numeric,
    concentrationunits text,
    storagestatus text,
    previousstoragestatus text,
    deviations text,
    treatments text,
    allocatedforaddressid text,
    allocatedforaddresstype text,
    allocatedfordepartmentid text,
    preptypeid text,
    storagedisposalstatus text,
    reagentlotid text,
    qcsampletype text,
    specimentype text,
    disposaltargetdt timestamp with time zone,
    sourcespid text,
    sourcespversionid text,
    sourcesplevelid text,
    sourcespsourcelabel text,
    batchstageid text,
    activeflag text,
    productversionid text,
    instrumentid text,
    workorderid text,
    classification text,
    samplesubtypeid text,
    duedtoffset numeric,
    duedtoffsettimeunit text,
    duedtoverrideflag text,
    sourcesdiworkitemid text,
    requestitemid text,
    requestitemdetailid text,
    cancelleddt timestamp with time zone,
    cancelledby text,
    sdiworkitemcompletionstatus text,
    scheduletemplateflag text,
    eventnum numeric,
    processinstruction text,
    processtype text,
    monitorgroupid text,
    locationpath text,
    samplepointinstance numeric,
    materialid text,
    processingstartdt timestamp with time zone,
    processingenddt timestamp with time zone,
    wapstatus text,
    testingdepartmentid text,
    workareadepartmentid text,
    assignedanalystid text,
    assigneddepartmentid text,
    sitedepartmentid text,
    plannedstartdt timestamp with time zone,
    securityuser text,
    securitydepartment text,
    u_receivedby text,
    u_receiveddate timestamp with time zone,
    u_skipreviewflag text,
    u_sampletype text,
    u_exceptionflag text,
    u_samplingrequest text,
    u_samplingreqversionid text,
    u_testexpireddt timestamp with time zone,
    u_testexpiredflag text,
    u_collectdeparment text,
    u_autodepartreceiveflag text,
    u_autocheckflag text,
    u_assignedcollectby text,
    u_testresult text,
    u_batchstatus text,
    u_autoreceivelab text,
    u_autocollect text,
    u_pullsamplenum text,
    u_thflag text,
    u_samplerecord text,
    u_resamplingflag text,
    u_resampleid text,
    u_senddt timestamp with time zone,
    u_skiprecstatus text,
    u_storageenvid text,
    u_appflowid text,
    u_approveflowid text,
    u_sampleapprovestatus text,
    securityset text,
    u_sampletemplateversion text,
    u_retestedflag text,
    u_remeasuredreplicate numeric,
    u_finalresultflag text,
    u_confirmflag text,
    u_remeasuredflag text,
    u_parentsampleid text,
    u_resampleflag text,
    u_sampbatchid text,
    u_monitorsampleid text,
    u_batchno text,
    u_lessampleflag text,
    u_sampletemplate text,
    u_sendby text,
    u_releaseby text,
    u_releasedt timestamp with time zone,
    u_formincidentid text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sdidata; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.sdidata (
    sdcid text NOT NULL,
    keyid1 text NOT NULL,
    keyid2 text NOT NULL,
    keyid3 text NOT NULL,
    paramlistid text NOT NULL,
    paramlistversionid text NOT NULL,
    variantid text NOT NULL,
    dataset numeric NOT NULL,
    limitruleid text,
    limitruleversionid text,
    modifiableflag text,
    approvalsequenceflag text,
    approvalpassrule text,
    condition text,
    availabilityflag text,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    s_datasetstatus text,
    modtool text,
    s_notebookreference text,
    s_assignedanalyst text,
    s_instrumentid text,
    s_retestedflag text,
    s_icoverriddenflag text,
    s_remeasuredflag text,
    s_remeasureinstance numeric,
    s_qcbatchid text,
    s_qcbatchitemid text,
    trackitemid text,
    scheduleplanid text,
    scheduleplanitemid text,
    uniquenessflag text,
    approvalflag text,
    sdidataid text,
    sourceworkitemid text,
    sourceworkiteminstance numeric,
    s_cancellableflag text,
    documentid text,
    documentversionid text,
    blockflag text,
    activeflag text,
    s_assigneddepartment text,
    s_instrumentusedflag text,
    arraymethodid text,
    arraymethodversionid text,
    completeddt timestamp with time zone,
    completedby text,
    arraymethodinstance numeric,
    starteddt timestamp with time zone,
    arraymethodreviewdisposition text,
    startedby text,
    cancelleddt timestamp with time zone,
    cancelledby text,
    accreditedflag text,
    wapstatus text,
    testingdepartmentid text,
    workareadepartmentid text,
    plannedstartdt timestamp with time zone,
    u_returntodeflag text,
    u_pltype text,
    u_fromsampleid text,
    u_applyqcflag text,
    u_releasedby text,
    u_releaseddt timestamp with time zone,
    securityuser text,
    securitydepartment text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sdidataitem; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.sdidataitem (
    sdcid text NOT NULL,
    keyid1 text NOT NULL,
    keyid2 text NOT NULL,
    keyid3 text NOT NULL,
    paramlistid text NOT NULL,
    paramlistversionid text NOT NULL,
    variantid text NOT NULL,
    dataset numeric NOT NULL,
    paramid text NOT NULL,
    paramtype text NOT NULL,
    replicateid numeric NOT NULL,
    aliasid text,
    mandatoryflag text,
    datatypes text,
    enteredvalue numeric,
    enteredtext text,
    enteredunits text,
    operatorrule text,
    transformvalue numeric,
    transformdt timestamp with time zone,
    transformtext text,
    transformrule text,
    displayvalue text,
    displayunits text,
    displayformat text,
    enteredoperator text,
    enteredqualifier text,
    entrysdcid text,
    entryreftypeid text,
    calcrule text,
    measurementactionid text,
    releasedflag text,
    valuestatus text,
    condition text,
    transformdeferflag text,
    textcolor numeric,
    usersequence numeric,
    notes text,
    auditsequence numeric,
    tracelogid text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    s_acoverriddenflag text,
    modtool text,
    s_analystid text,
    s_qcevalstatus text,
    displayvalueformat text,
    calcexcludeflag text,
    sdidataitemid text,
    instrumentid text,
    instrumentfieldid text,
    activeflag text,
    externalreference text,
    resulttimeoffset numeric,
    defaultvalue text,
    uncertaintyvalue numeric,
    uncertaintydisplayvalue text,
    uncertaintyasymmetricflag text,
    uncertaintyvalueupper numeric,
    uncertaintydisplayvalueupper text,
    uncertaintyfunction text,
    uncertaintydisplayformat text,
    uncertaintyfunctionupper text,
    uncertaintydisplayformatupper text,
    reportflag text,
    qctransferflag text,
    u_fromsampleid text,
    u_returnflag text,
    empowerexp text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sdiworkitem; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.sdiworkitem (
    sdcid text NOT NULL,
    keyid1 text NOT NULL,
    keyid2 text NOT NULL,
    keyid3 text NOT NULL,
    workitemid text NOT NULL,
    workiteminstance numeric NOT NULL,
    workitemtypeflag text,
    groupid text,
    groupinstance numeric,
    appliedflag text,
    completeflag text,
    usersequence numeric,
    auditsequence numeric,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    s_shippeddt timestamp with time zone,
    s_shippableflag text,
    s_retestinstance numeric,
    s_retestedflag text,
    tracelogid text,
    duedt timestamp with time zone,
    trackitemid text,
    scheduleplanid text,
    scheduleplanitemid text,
    modtool text,
    modby text,
    moddt timestamp with time zone,
    s_assaytypeid text,
    s_sampletypeid text,
    sdiworkitemid text,
    documentid text,
    documentversionid text,
    activeflag text,
    s_assignedanalyst text,
    s_assigneddepartment text,
    workitemstatus text,
    duedtoffset numeric,
    workitemversionid text,
    duedtoffsettimeunit text,
    duedtoverrideflag text,
    sourcesstudyid text,
    childsampleplanappliedflag text,
    embedchildsampleplanid text,
    embedchildsampleplanversionid text,
    completeddt timestamp with time zone,
    applieddt timestamp with time zone,
    starteddt timestamp with time zone,
    cancelleddt timestamp with time zone,
    completedby text,
    appliedby text,
    startedby text,
    cancelledby text,
    applyonaddflag text,
    reflexrule text,
    wapstatus text,
    testingdepartmentid text,
    workareadepartmentid text,
    plannedstartdt timestamp with time zone,
    u_volumeunit text,
    u_volume numeric,
    u_releaseddt timestamp with time zone,
    u_releasedby text,
    u_iscurrentflag text,
    u_witype text,
    u_priority text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sdiworkitemitem; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.sdiworkitemitem (
    sdcid text NOT NULL,
    keyid1 text NOT NULL,
    keyid2 text NOT NULL,
    keyid3 text NOT NULL,
    workitemid text NOT NULL,
    workiteminstance numeric NOT NULL,
    workitemitemid text NOT NULL,
    itemsdcid text,
    itemkeyid1 text,
    itemkeyid2 text,
    itemkeyid3 text,
    iteminstance numeric,
    mandatoryflag text,
    completeflag text,
    usersequence numeric,
    auditsequence numeric,
    tracelogid text,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    modtool text,
    workitemitemrule text,
    forcenewflag text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: workitem; Type: TABLE; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE TABLE raw_gmp_lims_labvantage.workitem (
    workitemid text NOT NULL,
    workitemdesc text,
    workitemtypeflag text,
    notes text,
    auditsequence numeric,
    tracelogid text,
    templateflag text,
    usersequence numeric,
    createdt timestamp with time zone,
    createby text,
    createtool text,
    moddt timestamp with time zone,
    modby text,
    modtool text,
    s_shippableflag text,
    testingdepartmentid text,
    duedtoffset numeric,
    duedtoffsettimeunit text,
    quantity numeric,
    quantityunits text,
    quantitytype text,
    containerspertestflag text,
    containersperrepeatflag text,
    numrepeats numeric,
    destructivetestflag text,
    reusecontainerflag text,
    createworksheetrule text,
    activeflag text,
    workitemversionid text NOT NULL,
    embedchildsampleplanid text,
    versionstatus text,
    embedchildsampleplanversionid text,
    applicablesampletypeid text,
    autoapplyflag text,
    applychildplanonapplywiflag text,
    supportembeddedchildplanflag text,
    versionapproveddt timestamp with time zone,
    versioneffectivedt timestamp with time zone,
    workitemuseflag text,
    maxactivitysize numeric,
    createactivityrule text,
    workareadepartmentid text,
    autoassignanalystid text,
    createlesrule text,
    autoassignrule text,
    testinglabtype text,
    workareatype text,
    s_departmentid text,
    securityuser text,
    securitydepartment text,
    u_assigndifflag text,
    u_expirydt timestamp with time zone,
    u_classification text,
    u_orientation text,
    u_width numeric,
    u_height numeric,
    u_qccalcflag text,
    u_worksheetid text,
    u_worksheetversionid text,
    u_trainingreqflag text,
    u_publicreportgroupid text,
    u_approvalflow text,
    u_approvalstatus text,
    u_approvalflowby text,
    u_keyflag text,
    u_witype text,
    u_expectedamountunit text,
    u_expectedamount numeric,
    u_inspectiontime text,
    _lims_extracted_at timestamp with time zone,
    _etl_loaded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: mv_lv_result_explore; Type: MATERIALIZED VIEW; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE MATERIALIZED VIEW raw_gmp_lims_labvantage.mv_lv_result_explore AS
 SELECT DISTINCT ON (sdi.sdcid, sdi.keyid1, sdi.keyid2, sdi.keyid3, sdi.paramlistid, sdi.paramlistversionid, sdi.variantid, sdi.dataset, sdi.paramid, sdi.paramtype, sdi.replicateid) sdi.keyid1 AS s_sampleid,
    s.sampledesc,
    "substring"(s.productid, '^[0-9][0-9][0-9][0-9][0-9]'::text) AS material_code,
    pm.product_name,
    s.productid,
    s.sampletypeid,
    s.samplesubtypeid,
    s.samplestatus,
    s.u_finalresultflag,
    s.receiveddt,
    s.starttestingdt,
    s.duedt,
    s.revieweddt,
    s.reviewedby,
    s.reviewremarks,
    s.studyid,
    s.conditionlabel,
    s.schedulerulelabel,
    s.duedtoffset,
    s.batchid,
    COALESCE(b.u_batchno, s.u_batchno) AS u_batchno,
    b.batchtype,
    b.disposition AS batch_disposition,
    b.templateflag AS batch_templateflag,
    b.batchstatus,
    b.u_productdesc AS batch_productdesc,
    b.releaseddt AS batch_releaseddt,
    b.manufacturedt,
    b.expirydt,
    sw.workitemid,
    w.workitemdesc,
        CASE
            WHEN ((sw.workitemid = sd.paramlistid) AND (sd.variantid = '1'::text)) THEN sw.workitemid
            WHEN ((sw.workitemid = sd.paramlistid) AND (sd.variantid <> '1'::text)) THEN (((sw.workitemid || ' ('::text) || sd.variantid) || ')'::text)
            WHEN ((sw.workitemid <> sd.paramlistid) AND (sd.variantid = '1'::text)) THEN ((sw.workitemid || ' '::text) || sd.paramlistid)
            WHEN ((sw.workitemid <> sd.paramlistid) AND (sd.variantid <> '1'::text)) THEN (((((sw.workitemid || ' '::text) || sd.paramlistid) || ' ('::text) || sd.variantid) || ')'::text)
            ELSE NULL::text
        END AS composite_test_method_id,
    sd.paramlistid,
    pl.paramlistdesc,
    pl.s_instrumenttype,
    sdi.variantid,
    sdi.dataset,
    sd.s_datasetstatus,
    sd.s_qcbatchid,
    sd.s_qcbatchitemid,
    sd.s_assignedanalyst AS dataset_analyst,
    sdi.paramid,
        CASE
            WHEN ((sdi.paramtype = 'Standard'::text) AND (pli.numreplicates = (1)::numeric)) THEN sdi.paramid
            WHEN ((sdi.paramtype <> 'Standard'::text) AND (pli.numreplicates = (1)::numeric)) THEN ((sdi.paramid || ' '::text) || sdi.paramtype)
            WHEN ((sdi.paramtype = 'Standard'::text) AND (pli.numreplicates <> (1)::numeric)) THEN ((sdi.paramid || ' Rep: '::text) || sdi.replicateid)
            WHEN ((sdi.paramtype <> 'Standard'::text) AND (pli.numreplicates <> (1)::numeric)) THEN ((((sdi.paramid || ' '::text) || sdi.paramtype) || ' Rep: '::text) || sdi.replicateid)
            ELSE NULL::text
        END AS composite_param_id,
    sdi.paramtype,
    sdi.replicateid,
    sdi.enteredvalue,
    sdi.enteredtext,
    sdi.transformvalue,
    sdi.transformtext,
    sdi.displayvalue,
    COALESCE(sdi.displayunits, sdi.enteredunits) AS unit,
        CASE
            WHEN (btrim(sdi.displayvalue) ~ '^-?[0-9]+([.][0-9]+)?%?$'::text) THEN (replace(btrim(sdi.displayvalue), '%'::text, ''::text))::numeric
            WHEN (sdi.enteredvalue IS NOT NULL) THEN sdi.enteredvalue
            WHEN (btrim(sdi.enteredtext) ~ '^-?[0-9]+([.][0-9]+)?%?$'::text) THEN (replace(btrim(sdi.enteredtext), '%'::text, ''::text))::numeric
            ELSE NULL::numeric
        END AS clean_value,
        CASE
            WHEN (NULLIF(btrim(COALESCE(sdi.displayunits, sdi.enteredunits)), ''::text) IS NOT NULL) THEN COALESCE(sdi.displayunits, sdi.enteredunits)
            WHEN ((btrim(sdi.displayvalue) ~ '^-?[0-9]+([.][0-9]+)?%$'::text) OR (btrim(sdi.enteredtext) ~ '^-?[0-9]+([.][0-9]+)?%$'::text)) THEN '%'::text
            WHEN ((sdi.paramid ~~ '%峰面积%'::text) AND (sdi.paramlistid ~ '(HPLC|UPLC|色谱|液相|毛细管|cIEF|电泳|CE-SDS)'::text)) THEN '%'::text
            ELSE NULL::text
        END AS clean_unit,
    sdi.datatypes,
    sdi.s_analystid AS result_analyst,
    sdi.releasedflag,
    sdi.valuestatus,
    sdi.calcexcludeflag,
    sdi.mandatoryflag,
    s.completedt,
    sdi.createdt AS result_createdt,
    sdi.sdidataitemid
   FROM ((((((((((raw_gmp_lims_labvantage.sdidataitem sdi
     JOIN raw_gmp_lims_labvantage.s_sample s ON ((s.s_sampleid = sdi.keyid1)))
     LEFT JOIN raw_gmp_lims_labvantage.s_batch b ON ((b.s_batchid = s.batchid)))
     LEFT JOIN ( VALUES ('71001'::text,'氟尿嘧啶注射液'::text), ('71002'::text,'注射用亚叶酸钙'::text), ('71003'::text,'盐酸伊立替康注射液'::text), ('71004'::text,'舒利迭'::text), ('71005'::text,'万托林'::text), ('71006'::text,'信必可都保'::text), ('71007'::text,'曲妥珠(赫赛汀)'::text), ('71008'::text,'英夫利西(类克)'::text), ('71009'::text,'托珠(雅美罗)'::text), ('71010'::text,'奥马珠(茁乐)'::text), ('71011'::text,'帕妥珠'::text), ('71012'::text,'帕尼单抗'::text), ('71013'::text,'纳武利尤(欧狄沃)'::text), ('71014'::text,'司库奇尤(可善挺)'::text), ('71015'::text,'卡那津(Ilaris)'::text), ('71016'::text,'注射用亚叶酸钙'::text), ('71017'::text,'阿法替尼(吉泰瑞)'::text), ('71018'::text,'维D2'::text), ('71019'::text,'维D滴剂'::text), ('71020'::text,'碳酸钙(盖舒泰)'::text), ('71021'::text,'安加维'::text), ('71022'::text,'钙尔奇600D'::text), ('71023'::text,'注射用亚叶酸钙'::text), ('71024'::text,'舒利迭'::text), ('71025'::text,'信必可都保'::text), ('71026'::text,'奥玛珠'::text), ('71027'::text,'西替利嗪'::text), ('71028'::text,'左西替利嗪'::text), ('71029'::text,'氯雷他定'::text), ('71030'::text,'地氯雷他定'::text), ('71031'::text,'非索非那定'::text), ('72001'::text,'地舒(Xgeva)'::text), ('72002'::text,'美泊利'::text), ('72003'::text,'乌司奴(喜达诺)'::text), ('72004'::text,'乌司奴(喜达诺)'::text), ('72005'::text,'帕博利珠(可瑞达)'::text), ('72006'::text,'奥马珠(茁乐)'::text), ('72007'::text,'西妥昔(爱必妥)'::text), ('72008'::text,'特泽普'::text), ('72009'::text,'阿达木(修美乐)'::text), ('72010'::text,'地舒(Prolia)'::text), ('72011'::text,'地舒(鲁可欣)'::text), ('72012'::text,'纳鲁索拜(津立泰)'::text), ('72013'::text,'地舒(迈利舒)'::text), ('72014'::text,'地舒(恒盖)'::text), ('72015'::text,'地舒(HLX14)'::text), ('72016'::text,'纳鲁索拜'::text), ('72017'::text,'度普利尤'::text), ('32001'::text,'注射用英夫利西单抗'::text), ('32003'::text,'注射用奥马珠α'::text), ('32004'::text,'注射用英夫利西单抗'::text), ('32006'::text,'注射用CMAB809'::text), ('32007'::text,'注射用奥马珠α'::text), ('33001'::text,'CMAB820注射液'::text), ('33002'::text,'西妥昔β注射液'::text), ('33004'::text,'托珠注射液'::text), ('33006'::text,'CMAB810注射液'::text), ('33007'::text,'CMAB819注射液'::text), ('33008'::text,'CMAB017注射液'::text), ('33009'::text,'CMAB017安慰剂'::text), ('33010'::text,'CMAB807X注射液'::text), ('34001'::text,'CMAB007注射液'::text), ('34002'::text,'CMAB015注射液'::text), ('34003'::text,'CMAB807注射液'::text), ('31001'::text,'CMAB820'::text), ('31002'::text,'英夫利西单抗'::text), ('31005'::text,'西妥昔β'::text), ('31006'::text,'奥马珠α'::text), ('31007'::text,'英夫利西单抗'::text), ('31008'::text,'CMAB819'::text), ('31010'::text,'托珠'::text), ('31012'::text,'CMAB809'::text), ('31013'::text,'CMAB810'::text), ('31015'::text,'CMAB017'::text), ('31016'::text,'CMAB007'::text), ('31017'::text,'CMAB015'::text), ('31018'::text,'CMAB807'::text)) pm(code, product_name) ON ((pm.code = "substring"(s.productid, '^[0-9][0-9][0-9][0-9][0-9]'::text))))
     JOIN raw_gmp_lims_labvantage.sdidata sd ON (((sd.sdcid = sdi.sdcid) AND (sd.keyid1 = sdi.keyid1) AND (sd.keyid2 = sdi.keyid2) AND (sd.keyid3 = sdi.keyid3) AND (sd.paramlistid = sdi.paramlistid) AND (sd.paramlistversionid = sdi.paramlistversionid) AND (sd.variantid = sdi.variantid) AND (sd.dataset = sdi.dataset))))
     JOIN raw_gmp_lims_labvantage.sdiworkitemitem swi ON (((swi.sdcid = sd.sdcid) AND (swi.keyid1 = sd.keyid1) AND (swi.keyid2 = sd.keyid2) AND (swi.keyid3 = sd.keyid3) AND (swi.itemsdcid = 'ParamList'::text) AND (swi.itemkeyid1 = sd.paramlistid) AND (swi.itemkeyid2 = sd.paramlistversionid) AND (swi.itemkeyid3 = sd.variantid) AND (swi.iteminstance = sd.dataset))))
     JOIN raw_gmp_lims_labvantage.sdiworkitem sw ON (((sw.sdcid = swi.sdcid) AND (sw.keyid1 = swi.keyid1) AND (sw.keyid2 = swi.keyid2) AND (sw.keyid3 = swi.keyid3) AND (sw.workitemid = swi.workitemid) AND (sw.workiteminstance = swi.workiteminstance))))
     LEFT JOIN raw_gmp_lims_labvantage.workitem w ON (((w.workitemid = sw.workitemid) AND (w.workitemversionid = sw.workitemversionid))))
     LEFT JOIN raw_gmp_lims_labvantage.paramlist pl ON (((pl.paramlistid = sd.paramlistid) AND (pl.paramlistversionid = sd.paramlistversionid) AND (pl.variantid = sd.variantid))))
     LEFT JOIN raw_gmp_lims_labvantage.param p ON ((p.paramid = sdi.paramid)))
     LEFT JOIN raw_gmp_lims_labvantage.paramlistitem pli ON (((pli.paramlistid = sdi.paramlistid) AND (pli.paramlistversionid = sdi.paramlistversionid) AND (pli.variantid = sdi.variantid) AND (pli.paramid = sdi.paramid) AND (pli.paramtype = sdi.paramtype))))
  WHERE ((sdi.sdcid = 'Sample'::text) AND (sw.workitemid <> '_Reflex'::text) AND ("substring"(s.productid, '^[0-9][0-9][0-9][0-9][0-9]'::text) = ANY (ARRAY['71001'::text, '71002'::text, '71003'::text, '71004'::text, '71005'::text, '71006'::text, '71007'::text, '71008'::text, '71009'::text, '71010'::text, '71011'::text, '71012'::text, '71013'::text, '71014'::text, '71015'::text, '71016'::text, '71017'::text, '71018'::text, '71019'::text, '71020'::text, '71021'::text, '71022'::text, '71023'::text, '71024'::text, '71025'::text, '71026'::text, '71027'::text, '71028'::text, '71029'::text, '71030'::text, '71031'::text, '72001'::text, '72002'::text, '72003'::text, '72004'::text, '72005'::text, '72006'::text, '72007'::text, '72008'::text, '72009'::text, '72010'::text, '72011'::text, '72012'::text, '72013'::text, '72014'::text, '72015'::text, '72016'::text, '72017'::text, '32001'::text, '32003'::text, '32004'::text, '32006'::text, '32007'::text, '33001'::text, '33002'::text, '33004'::text, '33006'::text, '33007'::text, '33008'::text, '33009'::text, '33010'::text, '34001'::text, '34002'::text, '34003'::text, '31001'::text, '31002'::text, '31005'::text, '31006'::text, '31007'::text, '31008'::text, '31010'::text, '31012'::text, '31013'::text, '31015'::text, '31016'::text, '31017'::text, '31018'::text])) AND (COALESCE(s.sampletypeid, ''::text) <> 'CleaningValidation'::text) AND (s.samplestatus = ANY (ARRAY['Reviewed'::text, 'Completed'::text])))
  ORDER BY sdi.sdcid, sdi.keyid1, sdi.keyid2, sdi.keyid3, sdi.paramlistid, sdi.paramlistversionid, sdi.variantid, sdi.dataset, sdi.paramid, sdi.paramtype, sdi.replicateid, sw.workiteminstance
  WITH NO DATA;


--
-- Name: access_audit_log access_id; Type: DEFAULT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.access_audit_log ALTER COLUMN access_id SET DEFAULT nextval('meta.access_audit_log_access_id_seq'::regclass);


--
-- Name: data_correction_log correction_id; Type: DEFAULT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.data_correction_log ALTER COLUMN correction_id SET DEFAULT nextval('meta.data_correction_log_correction_id_seq'::regclass);


--
-- Name: etl_run run_id; Type: DEFAULT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_run ALTER COLUMN run_id SET DEFAULT nextval('meta.etl_run_run_id_seq'::regclass);


--
-- Name: load_error_log error_id; Type: DEFAULT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.load_error_log ALTER COLUMN error_id SET DEFAULT nextval('meta.load_error_log_error_id_seq'::regclass);


--
-- Name: source_file_registry file_id; Type: DEFAULT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.source_file_registry ALTER COLUMN file_id SET DEFAULT nextval('meta.source_file_registry_file_id_seq'::regclass);


--
-- Name: access_audit_log access_audit_log_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.access_audit_log
    ADD CONSTRAINT access_audit_log_pkey PRIMARY KEY (access_id);


--
-- Name: data_correction_log data_correction_log_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.data_correction_log
    ADD CONSTRAINT data_correction_log_pkey PRIMARY KEY (correction_id);


--
-- Name: equipment_lookup equipment_lookup_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.equipment_lookup
    ADD CONSTRAINT equipment_lookup_pkey PRIMARY KEY (equipment_id);


--
-- Name: equipment_lookup equipment_lookup_source_instance_key; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.equipment_lookup
    ADD CONSTRAINT equipment_lookup_source_instance_key UNIQUE (source_instance);


--
-- Name: etl_job etl_job_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_job
    ADD CONSTRAINT etl_job_pkey PRIMARY KEY (job_name);


--
-- Name: etl_run etl_run_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_run
    ADD CONSTRAINT etl_run_pkey PRIMARY KEY (run_id);


--
-- Name: etl_watermark etl_watermark_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_watermark
    ADD CONSTRAINT etl_watermark_pkey PRIMARY KEY (job_name, source_system, source_instance, target_table);


--
-- Name: load_error_log load_error_log_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.load_error_log
    ADD CONSTRAINT load_error_log_pkey PRIMARY KEY (error_id);


--
-- Name: source_file_registry source_file_registry_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.source_file_registry
    ADD CONSTRAINT source_file_registry_pkey PRIMARY KEY (file_id);


--
-- Name: param param_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.param
    ADD CONSTRAINT param_pkey PRIMARY KEY (paramid);


--
-- Name: paramlist paramlist_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.paramlist
    ADD CONSTRAINT paramlist_pkey PRIMARY KEY (paramlistid, paramlistversionid, variantid);


--
-- Name: paramlistitem paramlistitem_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.paramlistitem
    ADD CONSTRAINT paramlistitem_pkey PRIMARY KEY (paramlistid, paramlistversionid, variantid, paramid, paramtype);


--
-- Name: s_batch s_batch_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.s_batch
    ADD CONSTRAINT s_batch_pkey PRIMARY KEY (s_batchid);


--
-- Name: s_sample s_sample_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.s_sample
    ADD CONSTRAINT s_sample_pkey PRIMARY KEY (s_sampleid);


--
-- Name: sdidata sdidata_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.sdidata
    ADD CONSTRAINT sdidata_pkey PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset);


--
-- Name: sdidataitem sdidataitem_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.sdidataitem
    ADD CONSTRAINT sdidataitem_pkey PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, paramlistid, paramlistversionid, variantid, dataset, paramid, paramtype, replicateid);


--
-- Name: sdiworkitem sdiworkitem_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.sdiworkitem
    ADD CONSTRAINT sdiworkitem_pkey PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, workitemid, workiteminstance);


--
-- Name: sdiworkitemitem sdiworkitemitem_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.sdiworkitemitem
    ADD CONSTRAINT sdiworkitemitem_pkey PRIMARY KEY (sdcid, keyid1, keyid2, keyid3, workitemid, workiteminstance, workitemitemid);


--
-- Name: workitem workitem_pkey; Type: CONSTRAINT; Schema: raw_gmp_lims_labvantage; Owner: -
--

ALTER TABLE ONLY raw_gmp_lims_labvantage.workitem
    ADD CONSTRAINT workitem_pkey PRIMARY KEY (workitemid, workitemversionid);


--
-- Name: idx_access_audit_time; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX idx_access_audit_time ON meta.access_audit_log USING btree (access_time);


--
-- Name: idx_etl_run_job; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX idx_etl_run_job ON meta.etl_run USING btree (job_name, run_started_at DESC);


--
-- Name: idx_load_error_run; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX idx_load_error_run ON meta.load_error_log USING btree (run_id, error_time);


--
-- Name: uq_source_file_hash; Type: INDEX; Schema: meta; Owner: -
--

CREATE UNIQUE INDEX uq_source_file_hash ON meta.source_file_registry USING btree (source_system, file_hash) WHERE (file_hash IS NOT NULL);


--
-- Name: ix_param_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_param_moddt ON raw_gmp_lims_labvantage.param USING btree (moddt);


--
-- Name: ix_paramlist_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_paramlist_moddt ON raw_gmp_lims_labvantage.paramlist USING btree (moddt);


--
-- Name: ix_paramlistitem_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_paramlistitem_moddt ON raw_gmp_lims_labvantage.paramlistitem USING btree (moddt);


--
-- Name: ix_s_batch_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_s_batch_moddt ON raw_gmp_lims_labvantage.s_batch USING btree (moddt);


--
-- Name: ix_s_batch_u_batchno; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_s_batch_u_batchno ON raw_gmp_lims_labvantage.s_batch USING btree (u_batchno);


--
-- Name: ix_s_sample_batchid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_s_sample_batchid ON raw_gmp_lims_labvantage.s_sample USING btree (batchid);


--
-- Name: ix_s_sample_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_s_sample_moddt ON raw_gmp_lims_labvantage.s_sample USING btree (moddt);


--
-- Name: ix_s_sample_u_batchno; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_s_sample_u_batchno ON raw_gmp_lims_labvantage.s_sample USING btree (u_batchno);


--
-- Name: ix_sdidata_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidata_moddt ON raw_gmp_lims_labvantage.sdidata USING btree (moddt);


--
-- Name: ix_sdidata_s_assignedanalyst; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidata_s_assignedanalyst ON raw_gmp_lims_labvantage.sdidata USING btree (s_assignedanalyst);


--
-- Name: ix_sdidata_s_instrumentid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidata_s_instrumentid ON raw_gmp_lims_labvantage.sdidata USING btree (s_instrumentid);


--
-- Name: ix_sdidata_s_qcbatchid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidata_s_qcbatchid ON raw_gmp_lims_labvantage.sdidata USING btree (s_qcbatchid);


--
-- Name: ix_sdidata_sdcid_keyid1; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidata_sdcid_keyid1 ON raw_gmp_lims_labvantage.sdidata USING btree (sdcid, keyid1);


--
-- Name: ix_sdidataitem_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidataitem_moddt ON raw_gmp_lims_labvantage.sdidataitem USING btree (moddt);


--
-- Name: ix_sdidataitem_paramid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidataitem_paramid ON raw_gmp_lims_labvantage.sdidataitem USING btree (paramid);


--
-- Name: ix_sdidataitem_paramlistid_paramid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidataitem_paramlistid_paramid ON raw_gmp_lims_labvantage.sdidataitem USING btree (paramlistid, paramid);


--
-- Name: ix_sdidataitem_sdcid_keyid1; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdidataitem_sdcid_keyid1 ON raw_gmp_lims_labvantage.sdidataitem USING btree (sdcid, keyid1);


--
-- Name: ix_sdiworkitem_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdiworkitem_moddt ON raw_gmp_lims_labvantage.sdiworkitem USING btree (moddt);


--
-- Name: ix_sdiworkitem_sdcid_keyid1; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdiworkitem_sdcid_keyid1 ON raw_gmp_lims_labvantage.sdiworkitem USING btree (sdcid, keyid1);


--
-- Name: ix_sdiworkitem_workitemid; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdiworkitem_workitemid ON raw_gmp_lims_labvantage.sdiworkitem USING btree (workitemid);


--
-- Name: ix_sdiworkitemitem_chain; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdiworkitemitem_chain ON raw_gmp_lims_labvantage.sdiworkitemitem USING btree (sdcid, keyid1, workitemid, workiteminstance);


--
-- Name: ix_sdiworkitemitem_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_sdiworkitemitem_moddt ON raw_gmp_lims_labvantage.sdiworkitemitem USING btree (moddt);


--
-- Name: ix_workitem_moddt; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX ix_workitem_moddt ON raw_gmp_lims_labvantage.workitem USING btree (moddt);


--
-- Name: mv_lv_result_explore_batchtype_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_batchtype_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (batchtype);


--
-- Name: mv_lv_result_explore_material_code_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_material_code_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (material_code);


--
-- Name: mv_lv_result_explore_paramtype_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_paramtype_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (paramtype);


--
-- Name: mv_lv_result_explore_product_name_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_product_name_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (product_name);


--
-- Name: mv_lv_result_explore_releasedflag_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_releasedflag_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (releasedflag);


--
-- Name: mv_lv_result_explore_s_sampleid_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_s_sampleid_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (s_sampleid);


--
-- Name: mv_lv_result_explore_sampletypeid_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_sampletypeid_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (sampletypeid);


--
-- Name: mv_lv_result_explore_valuestatus_idx; Type: INDEX; Schema: raw_gmp_lims_labvantage; Owner: -
--

CREATE INDEX mv_lv_result_explore_valuestatus_idx ON raw_gmp_lims_labvantage.mv_lv_result_explore USING btree (valuestatus);


--
-- PostgreSQL database dump complete
--

\unrestrict ngZofU87oV5VMqCINh2EBuXl8Sz2kdqNZh3ph4IxrocaTprCb7xgqeJzuboAvTI

