--
-- PostgreSQL database dump
--

\restrict ZZNQcc6EbL3cFoIG5hjfFp6od9HTqru2yZJnfddIHpzg3HTcDQFLfjz3ye6kqYM

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
-- Name: ext_gmp; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ext_gmp;


--
-- Name: ext_mdm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ext_mdm;


--
-- Name: ext_rd; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ext_rd;


--
-- Name: mart; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mart;


--
-- Name: mdm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mdm;


--
-- Name: SCHEMA mdm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA mdm IS 'LIMS 域内主数据(method / personnel)。本 schema 由 Dashboard 后端写,通过 mart.dim_* 视图对外暴露。看板和 cmab_mdm(公司级 MDM)正交,不与 cmab_mdm.auth.user 等表重叠。建立日期 2026-05-18,来源决策:见 migrations/README.md。';


--
-- Name: meta; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA meta;


--
-- Name: ml_features; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ml_features;


--
-- Name: reporting; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA reporting;


--
-- Name: snap_gmp; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA snap_gmp;


--
-- Name: snap_mdm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA snap_mdm;


--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA staging;


--
-- Name: postgres_fdw; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgres_fdw WITH SCHEMA public;


--
-- Name: EXTENSION postgres_fdw; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgres_fdw IS 'foreign-data wrapper for remote PostgreSQL servers';


--
-- Name: fn_biz_days(date, date); Type: FUNCTION; Schema: mart; Owner: -
--

CREATE FUNCTION mart.fn_biz_days(d_start date, d_end date) RETURNS integer
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT CASE
    WHEN d_start IS NULL OR d_end IS NULL OR d_end < d_start THEN NULL
    ELSE 5 * ((d_end - d_start) / 7)
       + (ARRAY[0,1,2,3,4,5,5,    -- 起始 DOW=0(周日)
                0,1,2,3,4,4,4,    -- DOW=1(周一)
                0,1,2,3,3,3,4,    -- DOW=2(周二)
                0,1,2,2,2,3,4,    -- DOW=3(周三)
                0,1,1,1,2,3,4,    -- DOW=4(周四)
                0,0,0,1,2,3,4,    -- DOW=5(周五)
                0,0,1,2,3,4,5])   -- DOW=6(周六)
         [EXTRACT(DOW FROM d_start)::int * 7 + ((d_end - d_start) % 7) + 1]
  END
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: personnel; Type: TABLE; Schema: mdm; Owner: -
--

CREATE TABLE mdm.personnel (
    employee_id character varying(32) NOT NULL,
    employee_name character varying(128) NOT NULL,
    department character varying(64) DEFAULT '药学及技术转移部'::character varying NOT NULL,
    group_id character varying(32),
    status character varying(16) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(64),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by character varying(64),
    deleted_at timestamp with time zone,
    deleted_by character varying(64),
    CONSTRAINT personnel_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'left'::character varying])::text[])))
);


--
-- Name: TABLE personnel; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON TABLE mdm.personnel IS 'LIMS 检测员名册主数据。迁自 rd_pg.cmc_mdm.mdm_core.employee_master (2026-05-18)。与 cmab_mdm.auth.user 正交 —— 后者是应用登录账号,本表是检测员人事名册(对应 raw LIMS 中的 tester/authoriser 字段值)。';


--
-- Name: COLUMN personnel.employee_id; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.personnel.employee_id IS '员工工号,业务主键,对应 raw LIMS tester/authoriser';


--
-- Name: COLUMN personnel.group_id; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.personnel.group_id IS '所属检验组(TT1/TT5/PD/...),Dashboard sidebar 检验组多选用此列过滤';


--
-- Name: COLUMN personnel.status; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.personnel.status IS 'active=在岗 / inactive=暂离 / left=离职';


--
-- Name: dim_employee; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.dim_employee AS
 SELECT (employee_id)::text AS employee_id,
    (employee_name)::text AS employee_name,
    (department)::text AS department,
    (group_id)::text AS group_id,
    (status)::text AS status
   FROM mdm.personnel
  WHERE (deleted_at IS NULL);


--
-- Name: VIEW dim_employee; Type: COMMENT; Schema: mart; Owner: -
--

COMMENT ON VIEW mart.dim_employee IS '检测员维度。2026-05-18 之前从 ext_legacy_meta.dim_employee (FDW → cmc_data_platform) 取数,之后改读 cmc_analytics.mdm.personnel 本地表。';


--
-- Name: test_method; Type: TABLE; Schema: mdm; Owner: -
--

CREATE TABLE mdm.test_method (
    method_code character varying(32) NOT NULL,
    method_name character varying(255) NOT NULL,
    std_minutes numeric(6,2),
    target_days integer,
    description text,
    status character varying(16) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(64),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by character varying(64),
    deleted_at timestamp with time zone,
    deleted_by character varying(64),
    CONSTRAINT test_method_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'retired'::character varying])::text[])))
);


--
-- Name: TABLE test_method; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON TABLE mdm.test_method IS 'LIMS 检验方法主数据。迁自 rd_pg.cmc_mdm.mdm_quality.method_master (2026-05-18)。由 Dashboard /api/v1/admin/methods 端点写,mart.dim_method 视图消费。';


--
-- Name: COLUMN test_method.method_code; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.test_method.method_code IS '方法编码,业务主键(QA 命名,稳定)';


--
-- Name: COLUMN test_method.std_minutes; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.test_method.std_minutes IS '标准检测工时(分钟),供工时统计';


--
-- Name: COLUMN test_method.target_days; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.test_method.target_days IS '目标周转天数,供超期判定';


--
-- Name: COLUMN test_method.status; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.test_method.status IS 'active=在用 / inactive=暂停 / retired=已废止';


--
-- Name: COLUMN test_method.created_by; Type: COMMENT; Schema: mdm; Owner: -
--

COMMENT ON COLUMN mdm.test_method.created_by IS 'admin 面板操作者名,允许空(过渡期 admin 端点暂未携带身份)';


--
-- Name: dim_method; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.dim_method AS
 SELECT (method_code)::text AS method_code,
    (method_name)::text AS method_name,
    std_minutes,
    target_days
   FROM mdm.test_method
  WHERE (deleted_at IS NULL);


--
-- Name: VIEW dim_method; Type: COMMENT; Schema: mart; Owner: -
--

COMMENT ON VIEW mart.dim_method IS '检验方法维度。2026-05-18 之前从 ext_legacy_meta.dim_method (FDW → cmc_data_platform) 取数,之后改读 cmc_analytics.mdm.test_method 本地表。列签名保持兼容(全 text)。';


--
-- Name: stg_sample; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.stg_sample (
    source_system text NOT NULL,
    source_id text NOT NULL,
    project_id text,
    sample_name text,
    request_dt timestamp without time zone,
    request_person text,
    sampled_dt timestamp without time zone,
    received_dt timestamp without time zone,
    status text,
    batch_number text,
    sample_type text,
    test_type text,
    production_line_id text,
    timepoint double precision,
    timepoint_unit text,
    started_dt timestamp without time zone,
    tester text,
    completed_dt timestamp without time zone,
    completer text,
    authorised_dt timestamp without time zone,
    authoriser text,
    group_id text
);


--
-- Name: stg_test; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.stg_test (
    source_system text NOT NULL,
    source_id text NOT NULL,
    source_sample_id text,
    method_code text,
    method_name text,
    started_dt timestamp without time zone,
    groupleader_received_dt timestamp without time zone,
    assigned_dt timestamp without time zone,
    tester text,
    status text,
    completed_dt timestamp without time zone,
    authorised_dt timestamp without time zone,
    authoriser text,
    group_id text,
    assigner text,
    completer text
);


--
-- Name: v_test_task_monitor; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_test_task_monitor AS
 SELECT t.source_id AS test_id,
    t.source_sample_id AS sample_id,
    s.project_id,
    s.sample_name,
    s.batch_number,
    s.sample_type,
    s.test_type,
    t.method_code,
    t.method_name,
    s.request_dt,
    s.received_dt AS sample_received_dt,
    t.groupleader_received_dt,
    t.assigned_dt,
    t.started_dt AS test_started_dt,
    t.completed_dt AS test_completed_dt,
    t.authorised_dt AS test_authorised_dt,
    t.tester,
    t.authoriser,
    t.group_id,
    s.status AS sample_status,
    t.status AS test_status,
        CASE
            WHEN (t.status = 'A'::text) THEN 'released'::text
            WHEN (t.status = 'C'::text) THEN 'completed'::text
            WHEN (t.status = 'V'::text) THEN 'in_progress'::text
            WHEN (t.status = ANY (ARRAY['U'::text, 'P'::text])) THEN 'not_started'::text
            WHEN (t.status = 'X'::text) THEN 'cancelled'::text
            ELSE 'unknown'::text
        END AS task_bucket,
    t.assigner,
    t.completer,
    (t.completer = 'IM_USER'::text) AS is_auto_completed,
    mart.fn_biz_days((s.received_dt)::date, (t.authorised_dt)::date) AS biz_days_cycle
   FROM (staging.stg_test t
     LEFT JOIN staging.stg_sample s ON (((s.source_system = t.source_system) AND (s.source_id = t.source_sample_id))))
  WHERE (t.source_system = 'rd_samplemanager'::text);


--
-- Name: v_completed_tests; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_completed_tests AS
 SELECT test_id,
    sample_id,
    project_id,
    sample_name,
    batch_number,
    sample_type,
    test_type,
    method_code,
    method_name,
    request_dt,
    sample_received_dt,
    groupleader_received_dt,
    assigned_dt,
    test_started_dt,
    test_completed_dt,
    test_authorised_dt,
    tester,
    authoriser,
    group_id,
    sample_status,
    test_status,
    task_bucket
   FROM mart.v_test_task_monitor
  WHERE ((test_authorised_dt IS NOT NULL) AND ((test_status IS NULL) OR (upper(test_status) <> 'X'::text)));


--
-- Name: v_daily_workload; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_daily_workload AS
 SELECT date(m.test_authorised_dt) AS stat_date,
    m.project_id,
    m.group_id,
    m.tester,
    m.method_code,
    m.method_name,
    count(*) AS completed_test_count,
    round((sum(COALESCE(tm.std_minutes, (0)::numeric)) / 60.0), 2) AS total_std_hours
   FROM (mart.v_test_task_monitor m
     LEFT JOIN mdm.test_method tm ON (((tm.method_code)::text = m.method_code)))
  WHERE ((m.test_authorised_dt IS NOT NULL) AND ((m.test_status IS NULL) OR (upper(m.test_status) <> 'X'::text)))
  GROUP BY (date(m.test_authorised_dt)), m.project_id, m.group_id, m.tester, m.method_code, m.method_name;


--
-- Name: v_overdue_snapshot; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_overdue_snapshot AS
 SELECT test_id,
    sample_id,
    project_id,
    sample_name,
    batch_number,
    sample_type,
    test_type,
    method_code,
    method_name,
    tester,
    authoriser,
    group_id,
    request_dt,
    sample_received_dt,
    groupleader_received_dt,
    assigned_dt,
    test_started_dt,
    test_completed_dt,
    test_authorised_dt,
    sample_status,
    test_status,
    task_bucket,
        CASE
            WHEN (sample_status = 'U'::text) THEN 'unsubmitted'::text
            WHEN ((sample_status = ANY (ARRAY['V'::text, 'C'::text, 'A'::text])) AND (assigned_dt IS NULL)) THEN 'unassigned'::text
            WHEN ((assigned_dt IS NOT NULL) AND (test_completed_dt IS NULL) AND (test_status <> 'X'::text)) THEN 'inprogress'::text
            WHEN ((test_completed_dt IS NOT NULL) AND (test_authorised_dt IS NULL)) THEN 'unauthorized'::text
            ELSE 'other'::text
        END AS overdue_bucket
   FROM mart.v_test_task_monitor
  WHERE ((test_authorised_dt IS NULL) AND ((test_status IS NULL) OR (upper(test_status) <> 'X'::text)));


--
-- Name: v_pending_tests; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_pending_tests AS
 SELECT test_id,
    sample_id,
    project_id,
    sample_name,
    batch_number,
    sample_type,
    test_type,
    method_code,
    method_name,
    request_dt,
    sample_received_dt,
    groupleader_received_dt,
    assigned_dt,
    test_started_dt,
    test_completed_dt,
    test_authorised_dt,
    tester,
    authoriser,
    group_id,
    sample_status,
    test_status,
    task_bucket
   FROM mart.v_test_task_monitor
  WHERE ((test_authorised_dt IS NULL) AND ((sample_status IS NULL) OR (upper(sample_status) <> ALL (ARRAY['X'::text, 'U'::text]))) AND ((test_status IS NULL) OR (upper(test_status) <> ALL (ARRAY['X'::text, 'U'::text]))));


--
-- Name: v_sample_overview; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_sample_overview AS
 SELECT source_id AS sample_id,
    project_id,
    sample_name,
    batch_number,
    sample_type,
    test_type,
    request_dt,
    request_person,
    sampled_dt,
    received_dt,
    started_dt,
    completed_dt,
    authorised_dt,
    tester,
    completer,
    authoriser,
    group_id,
    status
   FROM staging.stg_sample s
  WHERE (source_system = 'rd_samplemanager'::text);


--
-- Name: v_turnaround_time; Type: VIEW; Schema: mart; Owner: -
--

CREATE VIEW mart.v_turnaround_time AS
 SELECT test_id,
    sample_id,
    project_id,
    sample_name,
    batch_number,
    sample_type,
    test_type,
    method_code,
    method_name,
    tester,
    authoriser,
    group_id,
    sample_status,
    test_status,
    request_dt,
    sample_received_dt,
    groupleader_received_dt,
    assigned_dt,
    test_started_dt,
    test_completed_dt,
    test_authorised_dt,
        CASE
            WHEN ((sample_received_dt IS NOT NULL) AND (groupleader_received_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (groupleader_received_dt - sample_received_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_receive_to_grouplead,
        CASE
            WHEN ((groupleader_received_dt IS NOT NULL) AND (assigned_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (assigned_dt - groupleader_received_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_grouplead_to_assign,
        CASE
            WHEN ((assigned_dt IS NOT NULL) AND (test_started_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (test_started_dt - assigned_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_assign_to_start,
        CASE
            WHEN ((test_started_dt IS NOT NULL) AND (test_completed_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (test_completed_dt - test_started_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_start_to_complete,
        CASE
            WHEN ((test_completed_dt IS NOT NULL) AND (test_authorised_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (test_authorised_dt - test_completed_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_complete_to_authorise,
        CASE
            WHEN ((sample_received_dt IS NOT NULL) AND (test_authorised_dt IS NOT NULL)) THEN (EXTRACT(epoch FROM (test_authorised_dt - sample_received_dt)) / 3600.0)
            ELSE NULL::numeric
        END AS hr_total_tat,
    biz_days_cycle
   FROM mart.v_test_task_monitor;


--
-- Name: stg_result; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.stg_result (
    source_system text NOT NULL,
    source_id text NOT NULL,
    source_test_id text,
    attribute text,
    order_no text,
    result_entered_dt timestamp without time zone,
    result_authorised_dt timestamp without time zone,
    authoriser text,
    value_num double precision,
    result_type text,
    value_str text,
    unit text,
    judgement text,
    updated_at timestamp without time zone
);


--
-- Name: personnel personnel_pkey; Type: CONSTRAINT; Schema: mdm; Owner: -
--

ALTER TABLE ONLY mdm.personnel
    ADD CONSTRAINT personnel_pkey PRIMARY KEY (employee_id);


--
-- Name: test_method test_method_pkey; Type: CONSTRAINT; Schema: mdm; Owner: -
--

ALTER TABLE ONLY mdm.test_method
    ADD CONSTRAINT test_method_pkey PRIMARY KEY (method_code);


--
-- Name: stg_result stg_result_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.stg_result
    ADD CONSTRAINT stg_result_pkey PRIMARY KEY (source_system, source_id);


--
-- Name: stg_sample stg_sample_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.stg_sample
    ADD CONSTRAINT stg_sample_pkey PRIMARY KEY (source_system, source_id);


--
-- Name: stg_test stg_test_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.stg_test
    ADD CONSTRAINT stg_test_pkey PRIMARY KEY (source_system, source_id);


--
-- Name: ix_personnel_group; Type: INDEX; Schema: mdm; Owner: -
--

CREATE INDEX ix_personnel_group ON mdm.personnel USING btree (group_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_personnel_status; Type: INDEX; Schema: mdm; Owner: -
--

CREATE INDEX ix_personnel_status ON mdm.personnel USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_test_method_active; Type: INDEX; Schema: mdm; Owner: -
--

CREATE INDEX ix_test_method_active ON mdm.test_method USING btree (method_code) WHERE (deleted_at IS NULL);


--
-- Name: idx_stg_result_test; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_stg_result_test ON staging.stg_result USING btree (source_system, source_test_id);


--
-- Name: idx_stg_sample_batch; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_stg_sample_batch ON staging.stg_sample USING btree (batch_number);


--
-- Name: idx_stg_sample_received; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_stg_sample_received ON staging.stg_sample USING btree (received_dt);


--
-- Name: idx_stg_test_method; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_stg_test_method ON staging.stg_test USING btree (method_code);


--
-- Name: idx_stg_test_sample; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_stg_test_sample ON staging.stg_test USING btree (source_system, source_sample_id);


--
-- PostgreSQL database dump complete
--

\unrestrict ZZNQcc6EbL3cFoIG5hjfFp6od9HTqru2yZJnfddIHpzg3HTcDQFLfjz3ye6kqYM

