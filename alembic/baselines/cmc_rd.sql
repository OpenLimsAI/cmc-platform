--
-- PostgreSQL database dump
--

\restrict g2XwFiDlA0F3neqAH9cI7wXS3is237kauzJaZn0pWr1zwfC3dCmzFJOlsQfRciA

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
-- Name: raw_rd_lims_samplemanager; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_rd_lims_samplemanager;


--
-- Name: raw_rd_usp_lucullus; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_rd_usp_lucullus;


--
-- Name: SCHEMA raw_rd_usp_lucullus; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA raw_rd_usp_lucullus IS 'R&D 上游 Lucullus / Securecell 工作站原始数据。append-only，修正走 meta.data_correction_log。';


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
    source_table text NOT NULL,
    watermark_col text NOT NULL,
    last_watermark timestamp without time zone,
    last_run_id bigint,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


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
-- Name: result; Type: TABLE; Schema: raw_rd_lims_samplemanager; Owner: -
--

CREATE TABLE raw_rd_lims_samplemanager.result (
    result_id text NOT NULL,
    test_id text,
    test_number text,
    name text,
    order_number text,
    result_type text,
    units text,
    minimum double precision,
    maximum double precision,
    typical double precision,
    true_word text,
    false_word text,
    allowed_characters text,
    calculation text,
    value double precision,
    text text,
    places numeric,
    out_of_range text,
    status text,
    old_status text,
    entered_on timestamp without time zone,
    entered_by text,
    date_authorised timestamp without time zone,
    authoriser text,
    group_id text,
    security_flags numeric,
    sig_figs_number numeric,
    sig_figs_rounding numeric,
    sig_figs_filter text,
    rep_control text,
    minimum_pql double precision,
    maximum_pql double precision,
    less_than_pql text,
    greater_than_pql text,
    pql_calculation text,
    formula text,
    dilution_factor double precision,
    spike_value double precision,
    surrogate_mlp text,
    surrogate_mlp_version text,
    matrix_no numeric,
    matrix_name text,
    column_no numeric,
    column_name text,
    row_no numeric,
    row_name text,
    has_incidents text,
    instrument_used text,
    raw_result text,
    entity_criteria text,
    workflow_node text,
    u_coa_mlp text
);


--
-- Name: sample; Type: TABLE; Schema: raw_rd_lims_samplemanager; Owner: -
--

CREATE TABLE raw_rd_lims_samplemanager.sample (
    sample_id text NOT NULL,
    id_numeric text,
    id_text text,
    job_name text,
    status text,
    old_status text,
    compared text,
    on_spec text,
    re_sampled text,
    original_sample text,
    link_number numeric,
    login_date timestamp without time zone,
    login_by text,
    sampled_date timestamp without time zone,
    recd_date timestamp without time zone,
    date_started timestamp without time zone,
    starter text,
    dateresreq timestamp without time zone,
    date_completed timestamp without time zone,
    completer text,
    dateresavail timestamp without time zone,
    date_authorised timestamp without time zone,
    authoriser text,
    authorisation_notes text,
    product text,
    product_version text,
    grade_code text,
    tests_to_do numeric,
    on_wks text,
    project_id text,
    batch_name text,
    sampling_point text,
    sample_type text,
    sample_name text,
    description text,
    preparation text,
    hazard text,
    priority numeric,
    location_id text,
    customer_id text,
    invoice_number text,
    test_schedule text,
    template_id text,
    comp_prod_name text,
    comp_prod_ver text,
    comp_prod_grade text,
    standard text,
    standard_id text,
    standard_version text,
    inspection_header text,
    standard_type text,
    batch_id text,
    dynamic_product text,
    total_elements numeric,
    sampling_procedure text,
    replicate_link_no numeric,
    auto_validate text,
    has_incidents text,
    certificate text,
    substance text,
    workflow_node text,
    is_split text,
    is_composite text,
    has_split text,
    has_composite text,
    composite_status text,
    entity_template_id text,
    entity_template_version text,
    has_attachments text,
    ct_transferno text,
    u_samplename text,
    u_remark text,
    u_point text,
    ct_samplingquantity text,
    u_con text,
    u_mea_con text,
    ct_producttype text,
    ct_testtype text,
    ct_smp_status text,
    ct_smp_on timestamp without time zone,
    ct_samplingperson text,
    ct_samp_remark text,
    ct_location text,
    u_qc_review_stat text,
    u_qc_review_by text,
    u_qc_review_on timestamp without time zone,
    u_qc_review_note text,
    u_qc_authorise_stat text,
    u_qc_authorise_by text,
    u_qc_authorise_on timestamp without time zone,
    u_qc_authorise_note text,
    ct_gcxbdm text,
    ct_pytj text,
    ct_jyyj text,
    ct_batchno text,
    ct_prodate timestamp without time zone,
    ct_expdate timestamp without time zone,
    u_smp_status text,
    ct_test_status text,
    u_batch_quantity text,
    u_matrialno text,
    u_login_check text,
    u_login_check_by text,
    u_login_check_on timestamp without time zone,
    u_is_record text,
    u_is_urgent text,
    dep_date timestamp without time zone,
    retest_date timestamp without time zone,
    production_line_id text,
    timepoint numeric,
    timepoint_unit text,
    u_is_replace text,
    u_conclusion text,
    u_conclusion_by text,
    u_conclusion_on timestamp without time zone,
    u_grade text,
    u_stage text,
    u_timelength timestamp without time zone,
    u_quantity numeric,
    u_prepared_by text,
    u_storage_cond text,
    u_supplier text,
    u_manufacturer text,
    u_guige text,
    group_id text,
    u_test_status text,
    u_end_date timestamp without time zone,
    stab_study_id text,
    stability_sample text,
    layer_factor text,
    c_factor text,
    time_factor text,
    u_clinet text,
    u_address text,
    u_liaison text,
    u_phone text,
    u_email text
);


--
-- Name: test; Type: TABLE; Schema: raw_rd_lims_samplemanager; Owner: -
--

CREATE TABLE raw_rd_lims_samplemanager.test (
    test_id text NOT NULL,
    sample_id text,
    test_number text,
    analysis text,
    sample text,
    preparation text,
    test_count numeric,
    status text,
    old_status text,
    date_started timestamp without time zone,
    starter text,
    date_completed timestamp without time zone,
    completer text,
    date_authorised timestamp without time zone,
    authoriser text,
    component_replicates numeric,
    worksheet text,
    worksheet_position numeric,
    replicate_test text,
    instrument text,
    test_priority numeric,
    on_spec text,
    test_schedule text,
    order_num text,
    has_result_list text,
    component_list text,
    analysis_version text,
    preparation_batch text,
    instrument_batch text,
    parent_test text,
    inspection_header text,
    trigger_rule text,
    trigger_analysis text,
    stat_double_att_fail text,
    validation_status text,
    authorisation_comment text,
    auto_validate text,
    has_incidents text,
    instrument_type text,
    instrument_required text,
    workflow_node text,
    entity_template_id text,
    entity_template_version text,
    has_attachments text,
    group_id text,
    u_coa_rep text,
    u_review_status text,
    u_review_by text,
    u_review_by_pid text,
    u_review_on text,
    u_review_note text,
    u_review_date timestamp without time zone,
    u_authorise_status text,
    u_authorise_by text,
    u_authorise_on text,
    u_authorise_note text,
    u_authorise_date timestamp without time zone,
    u_grouplead_stat text,
    u_grouplead_by text,
    u_grouplead_on timestamp without time zone,
    u_person_stat text,
    u_person_by text,
    u_person_on timestamp without time zone,
    u_analdesc text
);


--
-- Name: attrunit_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.attrunit_src (
    attrid bigint NOT NULL,
    unitid bigint NOT NULL,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE attrunit_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.attrunit_src IS 'Lucullus 属性-单位映射（源：s_attrunittab）。';


--
-- Name: channel_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.channel_src (
    physdevid bigint NOT NULL,
    channelid bigint NOT NULL,
    transa double precision,
    transb double precision,
    range bigint,
    rangemin double precision,
    rangemax double precision,
    channelname text,
    measpoint text,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE channel_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.channel_src IS 'Lucullus 物理通道（源：s_channeltab）。';


--
-- Name: dataset_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.dataset_src (
    source_instance text NOT NULL,
    datasetid bigint NOT NULL,
    procid bigint,
    reacid bigint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE dataset_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.dataset_src IS 'Lucullus 数据集到工艺/反应器的映射（源：lucullus.s_datasettab）。';


--
-- Name: device_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.device_src (
    devid bigint NOT NULL,
    devtypeid bigint,
    ownerid bigint,
    devname text,
    enterprisedomainid bigint,
    originalid bigint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE device_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.device_src IS 'Lucullus 逻辑设备（源：s_devtab）。';


--
-- Name: devtype_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.devtype_src (
    devtypeid bigint NOT NULL,
    devtype bigint,
    transintv double precision,
    timeout double precision,
    multipleuse smallint,
    timeouterror bigint,
    protocolerror bigint,
    reserved bigint,
    devtypename text,
    drivername text,
    remark text,
    enterprisedomainid bigint,
    originalid bigint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE devtype_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.devtype_src IS 'Lucullus 设备类型（源：s_devtypetab）。';


--
-- Name: logiporttype_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.logiporttype_src (
    logiporttypeid bigint NOT NULL,
    variabletype bigint,
    enumtypeid bigint,
    defaultvalue double precision,
    datatype bigint,
    direction bigint,
    logstatus bigint,
    logmodus bigint,
    lograte double precision,
    deadband double precision,
    logiportunit bigint,
    logiportshortname text,
    logiportname text,
    remark text,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE logiporttype_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.logiporttype_src IS 'Lucullus 逻辑端口类型/通道字典（源：s_logiporttypetab）。';


--
-- Name: physdev_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.physdev_src (
    physdevid bigint NOT NULL,
    serverid bigint,
    devtype bigint,
    physportaddr text,
    isserver smallint,
    timeout double precision,
    transmode bigint,
    daemon bigint,
    isreadonly smallint,
    physdevname text,
    physdevtype bigint,
    drivername text,
    physportname text,
    remark text,
    properties text,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE physdev_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.physdev_src IS 'Lucullus 物理设备（源：s_physdevtab）。';


--
-- Name: portconfig_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.portconfig_src (
    devid bigint NOT NULL,
    subdevid bigint NOT NULL,
    logiporttypeid bigint NOT NULL,
    physdevid bigint NOT NULL,
    channelid bigint NOT NULL,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE portconfig_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.portconfig_src IS 'Lucullus 端口配置（源：s_portconfigtab）。';


--
-- Name: process_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.process_src (
    source_instance text NOT NULL,
    procid bigint NOT NULL,
    procattr1id bigint,
    procattr2id bigint,
    procattr3id bigint,
    procattr4id bigint,
    loadstatus bigint,
    operationid bigint,
    versionno bigint,
    runtimeid bigint,
    duration double precision,
    timeunit bigint,
    procname text,
    starttime timestamp without time zone,
    endtime timestamp without time zone,
    plannedstart timestamp without time zone,
    plannedend timestamp without time zone,
    cultivationstart timestamp without time zone,
    cultivationend timestamp without time zone,
    plannedcultivationstart timestamp without time zone,
    plannedcultivationend timestamp without time zone,
    runmode bigint,
    remark text,
    saveset bigint,
    archivehash text,
    enterprisedomainid bigint,
    originalid bigint,
    last_modification timestamp without time zone,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE process_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.process_src IS 'Lucullus 工艺批次主表（源：lucullus.s_proctab）。';


--
-- Name: reacconfig_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.reacconfig_src (
    source_instance text NOT NULL,
    reacid bigint NOT NULL,
    devid bigint NOT NULL,
    sharableid bigint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE reacconfig_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.reacconfig_src IS 'Lucullus 反应器配置（源：s_reacconfigtab）。';


--
-- Name: reactor_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.reactor_src (
    source_instance text NOT NULL,
    reacid bigint NOT NULL,
    processcellid bigint,
    workingvolume double precision,
    numflasks bigint,
    reacname text,
    reaclongname text,
    reacproducer text,
    reactype bigint,
    factoryname text,
    reaccodes text,
    remark text,
    enterprisedomainid bigint,
    originalid bigint,
    active smallint,
    lictype bigint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE reactor_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.reactor_src IS 'Lucullus 反应器主表（源：s_reactab）。';


--
-- Name: signal_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.signal_src (
    source_instance text NOT NULL,
    procstateid bigint NOT NULL,
    datasetid bigint,
    devtype bigint,
    devid bigint,
    subdevid bigint,
    stateid bigint,
    datatype bigint,
    noentries bigint,
    nodim bigint,
    datacomp bigint,
    isdefault smallint,
    rawid bigint,
    signalreplacementid bigint,
    x_min double precision,
    y_min double precision,
    y_max double precision,
    x_max double precision,
    last_modification timestamp without time zone,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE signal_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.signal_src IS 'Lucullus 信号头（不含 BLOB，时序在 signal_timeseries）。';


--
-- Name: signal_timeseries; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.signal_timeseries (
    source_system text NOT NULL,
    source_instance text NOT NULL,
    batch_id text,
    procid bigint NOT NULL,
    procname text,
    datasetid bigint NOT NULL,
    reacid bigint,
    reactor_name text,
    procstateid bigint NOT NULL,
    stateid bigint,
    channel_code text NOT NULL,
    channel_name text,
    unitid bigint,
    unitsymbol text,
    unitname text,
    time_hours double precision NOT NULL,
    time_days double precision,
    timestamp_from_starttime timestamp without time zone,
    value real,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE signal_timeseries; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.signal_timeseries IS 'Lucullus 工艺通道时序采样。每行 = 一个通道在某采样点的值。';


--
-- Name: COLUMN signal_timeseries.source_instance; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.source_instance IS '设备唯一标识，格式 <env>_<line>_<stage>_<vendor>_<seq>，例 rd_ws01_usp_lucullus_01。在 meta.equipment_lookup 中注册。';


--
-- Name: COLUMN signal_timeseries.batch_id; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.batch_id IS '公司全局批号（端到端统一）。Lucullus 当前由 procname 填充，将来由业务规则映射。';


--
-- Name: COLUMN signal_timeseries.channel_code; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.channel_code IS '通道短名（如 m_temp / sp_ph / m_do）。来自 logiportshortname。';


--
-- Name: COLUMN signal_timeseries.time_hours; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.time_hours IS '相对工艺起点的小时偏移量（来自 Lucullus BLOB time 数据）。';


--
-- Name: COLUMN signal_timeseries.value; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.value IS '采样值，float32（来自 Lucullus BLOB item 数据）。';


--
-- Name: COLUMN signal_timeseries.extract_run_id; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON COLUMN raw_rd_usp_lucullus.signal_timeseries.extract_run_id IS '写入本行的 ETL 运行 ID，关联 meta.etl_run。';


--
-- Name: unit_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.unit_src (
    unitid bigint NOT NULL,
    unitsymbol text,
    unitname text,
    formula text,
    ismaterialunit smallint,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE unit_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.unit_src IS 'Lucullus 单位字典（源：s_unittab）。';


--
-- Name: unitconversion_src; Type: TABLE; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE TABLE raw_rd_usp_lucullus.unitconversion_src (
    unitconversionid bigint NOT NULL,
    unit1 bigint,
    unit2 bigint,
    sourceoffset double precision,
    gain double precision,
    extract_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    extract_run_id bigint
);


--
-- Name: TABLE unitconversion_src; Type: COMMENT; Schema: raw_rd_usp_lucullus; Owner: -
--

COMMENT ON TABLE raw_rd_usp_lucullus.unitconversion_src IS 'Lucullus 单位换算（源：s_unitconversiontab）。';


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
    ADD CONSTRAINT etl_watermark_pkey PRIMARY KEY (job_name, source_table);


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
-- Name: result result_pkey; Type: CONSTRAINT; Schema: raw_rd_lims_samplemanager; Owner: -
--

ALTER TABLE ONLY raw_rd_lims_samplemanager.result
    ADD CONSTRAINT result_pkey PRIMARY KEY (result_id);


--
-- Name: sample sample_pkey; Type: CONSTRAINT; Schema: raw_rd_lims_samplemanager; Owner: -
--

ALTER TABLE ONLY raw_rd_lims_samplemanager.sample
    ADD CONSTRAINT sample_pkey PRIMARY KEY (sample_id);


--
-- Name: test test_pkey; Type: CONSTRAINT; Schema: raw_rd_lims_samplemanager; Owner: -
--

ALTER TABLE ONLY raw_rd_lims_samplemanager.test
    ADD CONSTRAINT test_pkey PRIMARY KEY (test_id);


--
-- Name: attrunit_src attrunit_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.attrunit_src
    ADD CONSTRAINT attrunit_src_pkey PRIMARY KEY (attrid, unitid);


--
-- Name: channel_src channel_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.channel_src
    ADD CONSTRAINT channel_src_pkey PRIMARY KEY (physdevid, channelid);


--
-- Name: dataset_src dataset_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.dataset_src
    ADD CONSTRAINT dataset_src_pkey PRIMARY KEY (source_instance, datasetid);


--
-- Name: device_src device_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.device_src
    ADD CONSTRAINT device_src_pkey PRIMARY KEY (devid);


--
-- Name: devtype_src devtype_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.devtype_src
    ADD CONSTRAINT devtype_src_pkey PRIMARY KEY (devtypeid);


--
-- Name: logiporttype_src logiporttype_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.logiporttype_src
    ADD CONSTRAINT logiporttype_src_pkey PRIMARY KEY (logiporttypeid);


--
-- Name: physdev_src physdev_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.physdev_src
    ADD CONSTRAINT physdev_src_pkey PRIMARY KEY (physdevid);


--
-- Name: portconfig_src portconfig_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.portconfig_src
    ADD CONSTRAINT portconfig_src_pkey PRIMARY KEY (devid, subdevid, logiporttypeid, physdevid, channelid);


--
-- Name: process_src process_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.process_src
    ADD CONSTRAINT process_src_pkey PRIMARY KEY (source_instance, procid);


--
-- Name: reacconfig_src reacconfig_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.reacconfig_src
    ADD CONSTRAINT reacconfig_src_pkey PRIMARY KEY (source_instance, reacid, devid);


--
-- Name: reactor_src reactor_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.reactor_src
    ADD CONSTRAINT reactor_src_pkey PRIMARY KEY (source_instance, reacid);


--
-- Name: signal_src signal_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.signal_src
    ADD CONSTRAINT signal_src_pkey PRIMARY KEY (source_instance, procstateid);


--
-- Name: signal_timeseries signal_timeseries_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.signal_timeseries
    ADD CONSTRAINT signal_timeseries_pkey PRIMARY KEY (source_system, source_instance, procstateid, time_hours);


--
-- Name: unit_src unit_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.unit_src
    ADD CONSTRAINT unit_src_pkey PRIMARY KEY (unitid);


--
-- Name: unitconversion_src unitconversion_src_pkey; Type: CONSTRAINT; Schema: raw_rd_usp_lucullus; Owner: -
--

ALTER TABLE ONLY raw_rd_usp_lucullus.unitconversion_src
    ADD CONSTRAINT unitconversion_src_pkey PRIMARY KEY (unitconversionid);


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
-- Name: idx_raw_sm_result_test; Type: INDEX; Schema: raw_rd_lims_samplemanager; Owner: -
--

CREATE INDEX idx_raw_sm_result_test ON raw_rd_lims_samplemanager.result USING btree (test_id);


--
-- Name: idx_raw_sm_test_sample; Type: INDEX; Schema: raw_rd_lims_samplemanager; Owner: -
--

CREATE INDEX idx_raw_sm_test_sample ON raw_rd_lims_samplemanager.test USING btree (sample_id);


--
-- Name: idx_signal_ts_batch; Type: INDEX; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE INDEX idx_signal_ts_batch ON raw_rd_usp_lucullus.signal_timeseries USING btree (batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: idx_signal_ts_channel; Type: INDEX; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE INDEX idx_signal_ts_channel ON raw_rd_usp_lucullus.signal_timeseries USING btree (channel_code, timestamp_from_starttime);


--
-- Name: idx_signal_ts_procid; Type: INDEX; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE INDEX idx_signal_ts_procid ON raw_rd_usp_lucullus.signal_timeseries USING btree (source_instance, procid);


--
-- Name: idx_signal_ts_ts; Type: INDEX; Schema: raw_rd_usp_lucullus; Owner: -
--

CREATE INDEX idx_signal_ts_ts ON raw_rd_usp_lucullus.signal_timeseries USING btree (timestamp_from_starttime);


--
-- PostgreSQL database dump complete
--

\unrestrict g2XwFiDlA0F3neqAH9cI7wXS3is237kauzJaZn0pWr1zwfC3dCmzFJOlsQfRciA

