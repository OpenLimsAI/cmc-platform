--
-- PostgreSQL database dump
--

\restrict 1llZVGJmR0MCbLbq895pPidNez4MU8tb4LQS0Wrj0zPpemClVbBIwjb4jyPpq3m

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
-- Name: cost_accounting; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA cost_accounting;


--
-- Name: equipment_mgmt; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA equipment_mgmt;


--
-- Name: material_mgmt; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA material_mgmt;


--
-- Name: dblink; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS dblink WITH SCHEMA public;


--
-- Name: EXTENSION dblink; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION dblink IS 'connect to other PostgreSQL databases from within a database';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: cost_accounting; Owner: -
--

CREATE FUNCTION cost_accounting.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: trg_set_updated_at(); Type: FUNCTION; Schema: material_mgmt; Owner: -
--

CREATE FUNCTION material_mgmt.trg_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bom_template_items; Type: TABLE; Schema: cost_accounting; Owner: -
--

CREATE TABLE cost_accounting.bom_template_items (
    id bigint NOT NULL,
    template_id bigint NOT NULL,
    material_id bigint NOT NULL,
    process_stage character varying(20),
    default_quantity numeric(14,4),
    default_cycles_used integer,
    sort_order integer DEFAULT 0,
    remark text,
    CONSTRAINT bom_template_items_default_cycles_used_check CHECK ((default_cycles_used >= 0)),
    CONSTRAINT bom_template_items_default_quantity_check CHECK ((default_quantity >= (0)::numeric))
);


--
-- Name: TABLE bom_template_items; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON TABLE cost_accounting.bom_template_items IS 'BOM 模板明细';


--
-- Name: bom_template_items_id_seq; Type: SEQUENCE; Schema: cost_accounting; Owner: -
--

CREATE SEQUENCE cost_accounting.bom_template_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bom_template_items_id_seq; Type: SEQUENCE OWNED BY; Schema: cost_accounting; Owner: -
--

ALTER SEQUENCE cost_accounting.bom_template_items_id_seq OWNED BY cost_accounting.bom_template_items.id;


--
-- Name: bom_templates; Type: TABLE; Schema: cost_accounting; Owner: -
--

CREATE TABLE cost_accounting.bom_templates (
    id bigint NOT NULL,
    template_code character varying(50) NOT NULL,
    template_name character varying(200) NOT NULL,
    product_code character varying(50),
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE bom_templates; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON TABLE cost_accounting.bom_templates IS 'BOM 模板主表 (可复用的物料清单)';


--
-- Name: bom_templates_id_seq; Type: SEQUENCE; Schema: cost_accounting; Owner: -
--

CREATE SEQUENCE cost_accounting.bom_templates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bom_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: cost_accounting; Owner: -
--

ALTER SEQUENCE cost_accounting.bom_templates_id_seq OWNED BY cost_accounting.bom_templates.id;


--
-- Name: materials; Type: TABLE; Schema: cost_accounting; Owner: -
--

CREATE TABLE cost_accounting.materials (
    id bigint NOT NULL,
    material_code character varying(50) NOT NULL,
    material_name character varying(200) NOT NULL,
    category character varying(50),
    grade character varying(50),
    vendor character varying(100),
    specification character varying(200),
    catalog_no character varying(100),
    unit character varying(20),
    pack_size character varying(100),
    material_type character varying(20),
    unit_price numeric(18,8),
    currency character varying(10) DEFAULT 'CNY'::character varying,
    default_cycles integer,
    origin character varying(20),
    remark text,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_reusable_cycles CHECK ((((material_type)::text IS DISTINCT FROM 'reusable'::text) OR (unit_price IS NULL) OR (default_cycles IS NOT NULL))),
    CONSTRAINT materials_default_cycles_check CHECK (((default_cycles IS NULL) OR (default_cycles > 0))),
    CONSTRAINT materials_material_type_check CHECK ((((material_type)::text = ANY ((ARRAY['single_use'::character varying, 'reusable'::character varying])::text[])) OR (material_type IS NULL))),
    CONSTRAINT materials_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'discontinued'::character varying, 'duplicate'::character varying])::text[]))),
    CONSTRAINT materials_unit_price_check CHECK (((unit_price IS NULL) OR (unit_price >= (0)::numeric)))
);


--
-- Name: TABLE materials; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON TABLE cost_accounting.materials IS '物料主数据 (基线: 公司标准物料代码表)';


--
-- Name: COLUMN materials.material_code; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.material_code IS '业务键, 公司 5 位数字编码';


--
-- Name: COLUMN materials.grade; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.grade IS '级别, 来自标准代码表';


--
-- Name: COLUMN materials.pack_size; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.pack_size IS '包装规格 (如 12卷/箱)';


--
-- Name: COLUMN materials.material_type; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.material_type IS 'single_use=一次性, reusable=循环类, NULL=未分类(待录价时补)';


--
-- Name: COLUMN materials.unit_price; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.unit_price IS '单价, NULL=未录价 (视图中此时 cost_amount=NULL)';


--
-- Name: COLUMN materials.default_cycles; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.default_cycles IS '循环类物料的默认循环数';


--
-- Name: COLUMN materials.status; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.materials.status IS 'active=在用 / discontinued=停用 / duplicate=重复(已停用)';


--
-- Name: materials_id_seq; Type: SEQUENCE; Schema: cost_accounting; Owner: -
--

CREATE SEQUENCE cost_accounting.materials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materials_id_seq; Type: SEQUENCE OWNED BY; Schema: cost_accounting; Owner: -
--

ALTER SEQUENCE cost_accounting.materials_id_seq OWNED BY cost_accounting.materials.id;


--
-- Name: project_bom_items; Type: TABLE; Schema: cost_accounting; Owner: -
--

CREATE TABLE cost_accounting.project_bom_items (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    material_id bigint NOT NULL,
    process_stage character varying(20),
    quantity numeric(14,4),
    quantity_unit character varying(20),
    quantity_factor numeric(20,10),
    cycles_used integer,
    unit_price_snapshot numeric(14,4),
    sort_order integer DEFAULT 0,
    remark text,
    CONSTRAINT project_bom_items_cycles_used_check CHECK ((cycles_used >= 0)),
    CONSTRAINT project_bom_items_quantity_check CHECK ((quantity >= (0)::numeric))
);


--
-- Name: TABLE project_bom_items; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON TABLE cost_accounting.project_bom_items IS '项目 BOM 明细 (一次性用量 + 循环类配置)';


--
-- Name: COLUMN project_bom_items.unit_price_snapshot; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.project_bom_items.unit_price_snapshot IS 'V1 不使用, 预留: 后续支持历史价格回溯';


--
-- Name: project_bom_items_id_seq; Type: SEQUENCE; Schema: cost_accounting; Owner: -
--

CREATE SEQUENCE cost_accounting.project_bom_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_bom_items_id_seq; Type: SEQUENCE OWNED BY; Schema: cost_accounting; Owner: -
--

ALTER SEQUENCE cost_accounting.project_bom_items_id_seq OWNED BY cost_accounting.project_bom_items.id;


--
-- Name: projects; Type: TABLE; Schema: cost_accounting; Owner: -
--

CREATE TABLE cost_accounting.projects (
    id bigint NOT NULL,
    project_code character varying(50) NOT NULL,
    project_name character varying(200) NOT NULL,
    product_code character varying(50),
    template_id bigint,
    expression_titer numeric(10,4) NOT NULL,
    culture_volume numeric(10,2) NOT NULL,
    total_yield numeric(5,4) NOT NULL,
    bulk_concentration numeric(8,4),
    fill_volume_ml numeric(8,4),
    description text,
    status character varying(20) DEFAULT 'draft'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT projects_bulk_concentration_check CHECK ((bulk_concentration > (0)::numeric)),
    CONSTRAINT projects_culture_volume_check CHECK ((culture_volume > (0)::numeric)),
    CONSTRAINT projects_expression_titer_check CHECK ((expression_titer > (0)::numeric)),
    CONSTRAINT projects_fill_volume_ml_check CHECK ((fill_volume_ml > (0)::numeric)),
    CONSTRAINT projects_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'finalized'::character varying, 'archived'::character varying])::text[]))),
    CONSTRAINT projects_total_yield_check CHECK (((total_yield > (0)::numeric) AND (total_yield <= (1)::numeric)))
);


--
-- Name: TABLE projects; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON TABLE cost_accounting.projects IS '项目主表 (工艺参数 + 元信息)';


--
-- Name: COLUMN projects.expression_titer; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.projects.expression_titer IS '表达量 g/L';


--
-- Name: COLUMN projects.culture_volume; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.projects.culture_volume IS '培养体积 L';


--
-- Name: COLUMN projects.total_yield; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.projects.total_yield IS '总收率 0~1, 如 0.65 表示 65%';


--
-- Name: COLUMN projects.bulk_concentration; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.projects.bulk_concentration IS '原液浓度 g/L';


--
-- Name: COLUMN projects.fill_volume_ml; Type: COMMENT; Schema: cost_accounting; Owner: -
--

COMMENT ON COLUMN cost_accounting.projects.fill_volume_ml IS '单支装量 mL (制剂)';


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: cost_accounting; Owner: -
--

CREATE SEQUENCE cost_accounting.projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: cost_accounting; Owner: -
--

ALTER SEQUENCE cost_accounting.projects_id_seq OWNED BY cost_accounting.projects.id;


--
-- Name: v_material_usage_stats; Type: VIEW; Schema: cost_accounting; Owner: -
--

CREATE VIEW cost_accounting.v_material_usage_stats AS
SELECT
    NULL::bigint AS material_id,
    NULL::character varying(50) AS material_code,
    NULL::character varying(200) AS material_name,
    NULL::character varying(20) AS material_type,
    NULL::character varying(50) AS category,
    NULL::numeric(18,8) AS unit_price,
    NULL::character varying(20) AS status,
    NULL::bigint AS used_in_projects,
    NULL::numeric AS total_cost_contribution,
    NULL::numeric AS avg_cost_per_project;


--
-- Name: v_project_cost_detail; Type: VIEW; Schema: cost_accounting; Owner: -
--

CREATE VIEW cost_accounting.v_project_cost_detail AS
 SELECT pbi.id AS bom_item_id,
    pbi.project_id,
    p.project_code,
    p.project_name,
    pbi.material_id,
    m.material_code,
    m.material_name,
    m.material_type,
    m.category,
    pbi.process_stage,
    m.unit,
    m.unit_price,
    pbi.quantity,
    pbi.quantity_unit,
    pbi.quantity_factor,
    pbi.cycles_used,
    m.default_cycles,
        CASE
            WHEN (m.unit_price IS NULL) THEN NULL::numeric
            WHEN ((m.material_type)::text = 'single_use'::text) THEN ((COALESCE(pbi.quantity, (0)::numeric) * COALESCE(pbi.quantity_factor, (1)::numeric)) * m.unit_price)
            WHEN (((m.material_type)::text = 'reusable'::text) AND (m.default_cycles > 0)) THEN ((((COALESCE(pbi.quantity, (0)::numeric) * COALESCE(pbi.quantity_factor, (1)::numeric)) * m.unit_price) / (m.default_cycles)::numeric) * (COALESCE(pbi.cycles_used, 1))::numeric)
            ELSE NULL::numeric
        END AS cost_amount
   FROM ((cost_accounting.project_bom_items pbi
     JOIN cost_accounting.materials m ON ((m.id = pbi.material_id)))
     JOIN cost_accounting.projects p ON ((p.id = pbi.project_id)));


--
-- Name: v_project_summary; Type: VIEW; Schema: cost_accounting; Owner: -
--

CREATE VIEW cost_accounting.v_project_summary AS
SELECT
    NULL::bigint AS project_id,
    NULL::character varying(50) AS project_code,
    NULL::character varying(200) AS project_name,
    NULL::character varying(50) AS product_code,
    NULL::numeric(10,4) AS expression_titer,
    NULL::numeric(10,2) AS culture_volume,
    NULL::numeric(5,4) AS total_yield,
    NULL::numeric(8,4) AS bulk_concentration,
    NULL::numeric(8,4) AS fill_volume_ml,
    NULL::numeric AS bulk_yield_g,
    NULL::numeric AS total_cost,
    NULL::bigint AS missing_price_rows,
    NULL::numeric AS cost_per_gram,
    NULL::numeric AS cost_per_vial,
    NULL::character varying(20) AS status,
    NULL::timestamp with time zone AS created_at,
    NULL::timestamp with time zone AS updated_at;


--
-- Name: equipment; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment (
    equipment_id integer NOT NULL,
    equipment_code character varying(32) NOT NULL,
    name character varying(200) NOT NULL,
    category character varying(50) NOT NULL,
    model character varying(200),
    manufacturer character varying(100),
    serial_no character varying(100),
    location_room character varying(50),
    location_detail character varying(200),
    responsible_person character varying(50),
    status character varying(20) DEFAULT 'in_use'::character varying NOT NULL,
    purchase_date date,
    commission_date date,
    asset_value numeric(12,2),
    remark text,
    is_active boolean DEFAULT true NOT NULL,
    deactivated_at timestamp without time zone,
    deactivated_by character varying(50),
    deactivate_reason character varying(200),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(50),
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_by character varying(50),
    mdm_equipment_id bigint,
    data_source character varying(20) DEFAULT 'local'::character varying NOT NULL,
    CONSTRAINT ck_equipment_status CHECK (((status)::text = ANY ((ARRAY['in_use'::character varying, 'out_of_service'::character varying, 'scrapped'::character varying, 'in_repair'::character varying, 'in_calibration'::character varying])::text[])))
);


--
-- Name: equipment_attachment; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_attachment (
    attachment_id integer NOT NULL,
    equipment_id integer NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path character varying(500) NOT NULL,
    file_size integer,
    file_type character varying(20),
    tag character varying(30),
    description character varying(200),
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    uploaded_by character varying(50),
    CONSTRAINT ck_attachment_tag CHECK (((tag IS NULL) OR ((tag)::text = ANY ((ARRAY['sop'::character varying, 'certificate'::character varying, 'contract'::character varying, 'photo'::character varying, 'other'::character varying])::text[]))))
);


--
-- Name: equipment_attachment_attachment_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_attachment_attachment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_attachment_attachment_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_attachment_attachment_id_seq OWNED BY equipment_mgmt.equipment_attachment.attachment_id;


--
-- Name: equipment_calibration; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_calibration (
    calibration_id integer NOT NULL,
    equipment_id integer NOT NULL,
    calibration_date date NOT NULL,
    calibration_agency character varying(200),
    result character varying(20) NOT NULL,
    certificate_no character varying(100),
    next_calibration_date date,
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(50),
    CONSTRAINT ck_calibration_result CHECK (((result)::text = ANY ((ARRAY['qualified'::character varying, 'unqualified'::character varying, 'limited_use'::character varying])::text[])))
);


--
-- Name: equipment_calibration_calibration_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_calibration_calibration_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_calibration_calibration_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_calibration_calibration_id_seq OWNED BY equipment_mgmt.equipment_calibration.calibration_id;


--
-- Name: equipment_equipment_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_equipment_id_seq OWNED BY equipment_mgmt.equipment.equipment_id;


--
-- Name: equipment_maintenance; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_maintenance (
    maintenance_id integer NOT NULL,
    equipment_id integer NOT NULL,
    maintenance_date date NOT NULL,
    maintenance_type character varying(30) NOT NULL,
    content text,
    performed_by character varying(50) NOT NULL,
    next_maintenance_date date,
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(50),
    CONSTRAINT ck_maintenance_type CHECK (((maintenance_type)::text = ANY ((ARRAY['daily'::character varying, 'periodic'::character varying, 'special'::character varying])::text[])))
);


--
-- Name: equipment_maintenance_maintenance_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_maintenance_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_maintenance_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_maintenance_maintenance_id_seq OWNED BY equipment_mgmt.equipment_maintenance.maintenance_id;


--
-- Name: equipment_reminder; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_reminder (
    reminder_id integer NOT NULL,
    equipment_id integer NOT NULL,
    reminder_type character varying(30) NOT NULL,
    due_date date NOT NULL,
    advance_days integer DEFAULT 30 NOT NULL,
    is_resolved boolean DEFAULT false NOT NULL,
    resolved_at timestamp without time zone,
    resolved_by character varying(50),
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_reminder_type CHECK (((reminder_type)::text = ANY ((ARRAY['calibration'::character varying, 'maintenance'::character varying, 'warranty'::character varying])::text[])))
);


--
-- Name: equipment_reminder_reminder_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_reminder_reminder_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_reminder_reminder_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_reminder_reminder_id_seq OWNED BY equipment_mgmt.equipment_reminder.reminder_id;


--
-- Name: equipment_repair; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_repair (
    repair_id integer NOT NULL,
    equipment_id integer NOT NULL,
    report_date date NOT NULL,
    fault_description text NOT NULL,
    repair_provider character varying(200),
    repair_type character varying(20) DEFAULT 'external'::character varying NOT NULL,
    completion_date date,
    repair_cost numeric(12,2),
    conclusion text,
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by character varying(50),
    CONSTRAINT ck_repair_type CHECK (((repair_type)::text = ANY ((ARRAY['internal'::character varying, 'external'::character varying])::text[])))
);


--
-- Name: equipment_repair_repair_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_repair_repair_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_repair_repair_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_repair_repair_id_seq OWNED BY equipment_mgmt.equipment_repair.repair_id;


--
-- Name: equipment_warranty; Type: TABLE; Schema: equipment_mgmt; Owner: -
--

CREATE TABLE equipment_mgmt.equipment_warranty (
    warranty_id integer NOT NULL,
    equipment_id integer NOT NULL,
    warranty_start date NOT NULL,
    warranty_end date NOT NULL,
    warranty_scope text,
    provider_name character varying(200),
    provider_contact character varying(200),
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_warranty_dates CHECK ((warranty_end >= warranty_start))
);


--
-- Name: equipment_warranty_warranty_id_seq; Type: SEQUENCE; Schema: equipment_mgmt; Owner: -
--

CREATE SEQUENCE equipment_mgmt.equipment_warranty_warranty_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_warranty_warranty_id_seq; Type: SEQUENCE OWNED BY; Schema: equipment_mgmt; Owner: -
--

ALTER SEQUENCE equipment_mgmt.equipment_warranty_warranty_id_seq OWNED BY equipment_mgmt.equipment_warranty.warranty_id;


--
-- Name: app_user; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.app_user (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    must_change_password boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login_at timestamp without time zone,
    CONSTRAINT app_user_role_check CHECK (((role)::text = ANY (ARRAY[('admin'::character varying)::text, ('user'::character varying)::text])))
);


--
-- Name: app_user_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.app_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_user_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.app_user_id_seq OWNED BY material_mgmt.app_user.id;


--
-- Name: audit_log; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.audit_log (
    id bigint NOT NULL,
    user_id integer,
    username character varying(50),
    action character varying(50) NOT NULL,
    entity_type character varying(50),
    entity_id character varying(50),
    before_json jsonb,
    after_json jsonb,
    source_ip character varying(45),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.audit_log_id_seq OWNED BY material_mgmt.audit_log.id;


--
-- Name: auth_session; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.auth_session (
    token character varying(64) NOT NULL,
    user_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    last_seen_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    source_ip character varying(45)
);


--
-- Name: batch; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.batch (
    batch_id integer NOT NULL,
    batch_no character varying(100) NOT NULL,
    expiry_date date,
    location_id integer NOT NULL,
    received_date date NOT NULL,
    initial_qty numeric(12,2) NOT NULL,
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    material_id integer NOT NULL,
    intake_type character varying(20),
    concentration character varying(50),
    extinction_coefficient numeric(12,2),
    serial_no character varying(100),
    asset_no character varying(100),
    responsible_person character varying(50),
    CONSTRAINT ck_batch_intake_type CHECK (((intake_type IS NULL) OR ((intake_type)::text = ANY ((ARRAY['reagent'::character varying, 'consumable'::character varying, 'standard'::character varying, 'column'::character varying])::text[]))))
);


--
-- Name: batch_batch_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.batch_batch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: batch_batch_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.batch_batch_id_seq OWNED BY material_mgmt.batch.batch_id;


--
-- Name: category_dict; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.category_dict (
    category character varying(50) NOT NULL
);


--
-- Name: import_log; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.import_log (
    import_id integer NOT NULL,
    file_name character varying(200),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    operator character varying(50),
    total_rows integer DEFAULT 0,
    inserted_rows integer DEFAULT 0,
    updated_rows integer DEFAULT 0,
    failed_rows integer DEFAULT 0,
    error_detail jsonb
);


--
-- Name: import_log_import_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.import_log_import_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: import_log_import_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.import_log_import_id_seq OWNED BY material_mgmt.import_log.import_id;


--
-- Name: inventory_txn; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.inventory_txn (
    txn_id integer NOT NULL,
    batch_id integer NOT NULL,
    txn_type character varying(10) NOT NULL,
    qty numeric(12,2) NOT NULL,
    txn_date date NOT NULL,
    operator character varying(50) NOT NULL,
    purpose character varying(200),
    remark text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT inventory_txn_txn_type_check CHECK (((txn_type)::text = ANY ((ARRAY['IN'::character varying, 'OUT'::character varying, 'ADJUST'::character varying])::text[])))
);


--
-- Name: inventory_txn_txn_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.inventory_txn_txn_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventory_txn_txn_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.inventory_txn_txn_id_seq OWNED BY material_mgmt.inventory_txn.txn_id;


--
-- Name: location; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.location (
    location_id integer NOT NULL,
    storage_condition character varying(50),
    remark text,
    room_no character varying(20) NOT NULL,
    cabinet_no character varying(20) NOT NULL,
    layer_no smallint NOT NULL,
    name character varying(80) GENERATED ALWAYS AS ((((((room_no)::text || '-'::text) || (cabinet_no)::text) || '-L'::text) || layer_no)) STORED,
    CONSTRAINT ck_location_layer_positive CHECK ((layer_no >= 1))
);


--
-- Name: location_location_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.location_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: location_location_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.location_location_id_seq OWNED BY material_mgmt.location.location_id;


--
-- Name: material; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.material (
    material_code character varying(20) NOT NULL,
    category character varying(50),
    name_cn character varying(200) NOT NULL,
    grade character varying(50),
    manufacturer character varying(100),
    spec_model character varying(200),
    catalog_no character varying(100),
    unit character varying(20) NOT NULL,
    package_spec character varying(100),
    remark text,
    safety_stock numeric(12,2) DEFAULT 0,
    is_active boolean DEFAULT true,
    deactivated_at timestamp without time zone,
    deactivated_by character varying(50),
    deactivate_reason character varying(200),
    import_batch_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    hazard_class text[],
    material_id integer NOT NULL,
    material_type character varying(20),
    data_source character varying(10) DEFAULT 'local'::character varying,
    CONSTRAINT ck_material_type CHECK (((material_type IS NULL) OR ((material_type)::text = ANY ((ARRAY['reagent'::character varying, 'consumable'::character varying, 'standard'::character varying, 'column'::character varying])::text[])))),
    CONSTRAINT material_data_source_check CHECK (((data_source)::text = ANY ((ARRAY['mdm'::character varying, 'local'::character varying])::text[])))
);


--
-- Name: material_material_id_seq; Type: SEQUENCE; Schema: material_mgmt; Owner: -
--

CREATE SEQUENCE material_mgmt.material_material_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: material_material_id_seq; Type: SEQUENCE OWNED BY; Schema: material_mgmt; Owner: -
--

ALTER SEQUENCE material_mgmt.material_material_id_seq OWNED BY material_mgmt.material.material_id;


--
-- Name: unit_dict; Type: TABLE; Schema: material_mgmt; Owner: -
--

CREATE TABLE material_mgmt.unit_dict (
    unit character varying(20) NOT NULL,
    description character varying(100)
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: bom_template_items id; Type: DEFAULT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_template_items ALTER COLUMN id SET DEFAULT nextval('cost_accounting.bom_template_items_id_seq'::regclass);


--
-- Name: bom_templates id; Type: DEFAULT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_templates ALTER COLUMN id SET DEFAULT nextval('cost_accounting.bom_templates_id_seq'::regclass);


--
-- Name: materials id; Type: DEFAULT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.materials ALTER COLUMN id SET DEFAULT nextval('cost_accounting.materials_id_seq'::regclass);


--
-- Name: project_bom_items id; Type: DEFAULT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.project_bom_items ALTER COLUMN id SET DEFAULT nextval('cost_accounting.project_bom_items_id_seq'::regclass);


--
-- Name: projects id; Type: DEFAULT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.projects ALTER COLUMN id SET DEFAULT nextval('cost_accounting.projects_id_seq'::regclass);


--
-- Name: equipment equipment_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment ALTER COLUMN equipment_id SET DEFAULT nextval('equipment_mgmt.equipment_equipment_id_seq'::regclass);


--
-- Name: equipment_attachment attachment_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_attachment ALTER COLUMN attachment_id SET DEFAULT nextval('equipment_mgmt.equipment_attachment_attachment_id_seq'::regclass);


--
-- Name: equipment_calibration calibration_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_calibration ALTER COLUMN calibration_id SET DEFAULT nextval('equipment_mgmt.equipment_calibration_calibration_id_seq'::regclass);


--
-- Name: equipment_maintenance maintenance_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_maintenance ALTER COLUMN maintenance_id SET DEFAULT nextval('equipment_mgmt.equipment_maintenance_maintenance_id_seq'::regclass);


--
-- Name: equipment_reminder reminder_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_reminder ALTER COLUMN reminder_id SET DEFAULT nextval('equipment_mgmt.equipment_reminder_reminder_id_seq'::regclass);


--
-- Name: equipment_repair repair_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_repair ALTER COLUMN repair_id SET DEFAULT nextval('equipment_mgmt.equipment_repair_repair_id_seq'::regclass);


--
-- Name: equipment_warranty warranty_id; Type: DEFAULT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_warranty ALTER COLUMN warranty_id SET DEFAULT nextval('equipment_mgmt.equipment_warranty_warranty_id_seq'::regclass);


--
-- Name: app_user id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.app_user ALTER COLUMN id SET DEFAULT nextval('material_mgmt.app_user_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.audit_log ALTER COLUMN id SET DEFAULT nextval('material_mgmt.audit_log_id_seq'::regclass);


--
-- Name: batch batch_id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.batch ALTER COLUMN batch_id SET DEFAULT nextval('material_mgmt.batch_batch_id_seq'::regclass);


--
-- Name: import_log import_id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.import_log ALTER COLUMN import_id SET DEFAULT nextval('material_mgmt.import_log_import_id_seq'::regclass);


--
-- Name: inventory_txn txn_id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.inventory_txn ALTER COLUMN txn_id SET DEFAULT nextval('material_mgmt.inventory_txn_txn_id_seq'::regclass);


--
-- Name: location location_id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.location ALTER COLUMN location_id SET DEFAULT nextval('material_mgmt.location_location_id_seq'::regclass);


--
-- Name: material material_id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.material ALTER COLUMN material_id SET DEFAULT nextval('material_mgmt.material_material_id_seq'::regclass);


--
-- Name: bom_template_items bom_template_items_pkey; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_template_items
    ADD CONSTRAINT bom_template_items_pkey PRIMARY KEY (id);


--
-- Name: bom_template_items bom_template_items_template_id_material_id_process_stage_key; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_template_items
    ADD CONSTRAINT bom_template_items_template_id_material_id_process_stage_key UNIQUE (template_id, material_id, process_stage);


--
-- Name: bom_templates bom_templates_pkey; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_templates
    ADD CONSTRAINT bom_templates_pkey PRIMARY KEY (id);


--
-- Name: bom_templates bom_templates_template_code_key; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_templates
    ADD CONSTRAINT bom_templates_template_code_key UNIQUE (template_code);


--
-- Name: materials materials_material_code_key; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.materials
    ADD CONSTRAINT materials_material_code_key UNIQUE (material_code);


--
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- Name: project_bom_items project_bom_items_pkey; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.project_bom_items
    ADD CONSTRAINT project_bom_items_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: projects projects_project_code_key; Type: CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.projects
    ADD CONSTRAINT projects_project_code_key UNIQUE (project_code);


--
-- Name: equipment_attachment equipment_attachment_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_attachment
    ADD CONSTRAINT equipment_attachment_pkey PRIMARY KEY (attachment_id);


--
-- Name: equipment_calibration equipment_calibration_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_calibration
    ADD CONSTRAINT equipment_calibration_pkey PRIMARY KEY (calibration_id);


--
-- Name: equipment_maintenance equipment_maintenance_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_pkey PRIMARY KEY (maintenance_id);


--
-- Name: equipment equipment_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment
    ADD CONSTRAINT equipment_pkey PRIMARY KEY (equipment_id);


--
-- Name: equipment_reminder equipment_reminder_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_reminder
    ADD CONSTRAINT equipment_reminder_pkey PRIMARY KEY (reminder_id);


--
-- Name: equipment_repair equipment_repair_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_repair
    ADD CONSTRAINT equipment_repair_pkey PRIMARY KEY (repair_id);


--
-- Name: equipment_warranty equipment_warranty_pkey; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_warranty
    ADD CONSTRAINT equipment_warranty_pkey PRIMARY KEY (warranty_id);


--
-- Name: equipment uq_equipment_code; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment
    ADD CONSTRAINT uq_equipment_code UNIQUE (equipment_code);


--
-- Name: equipment_warranty uq_warranty_equipment; Type: CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_warranty
    ADD CONSTRAINT uq_warranty_equipment UNIQUE (equipment_id);


--
-- Name: app_user app_user_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.app_user
    ADD CONSTRAINT app_user_pkey PRIMARY KEY (id);


--
-- Name: app_user app_user_username_key; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.app_user
    ADD CONSTRAINT app_user_username_key UNIQUE (username);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: auth_session auth_session_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.auth_session
    ADD CONSTRAINT auth_session_pkey PRIMARY KEY (token);


--
-- Name: batch batch_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.batch
    ADD CONSTRAINT batch_pkey PRIMARY KEY (batch_id);


--
-- Name: category_dict category_dict_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.category_dict
    ADD CONSTRAINT category_dict_pkey PRIMARY KEY (category);


--
-- Name: import_log import_log_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.import_log
    ADD CONSTRAINT import_log_pkey PRIMARY KEY (import_id);


--
-- Name: inventory_txn inventory_txn_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.inventory_txn
    ADD CONSTRAINT inventory_txn_pkey PRIMARY KEY (txn_id);


--
-- Name: location location_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.location
    ADD CONSTRAINT location_pkey PRIMARY KEY (location_id);


--
-- Name: material material_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.material
    ADD CONSTRAINT material_pkey PRIMARY KEY (material_id);


--
-- Name: unit_dict unit_dict_pkey; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.unit_dict
    ADD CONSTRAINT unit_dict_pkey PRIMARY KEY (unit);


--
-- Name: batch uq_batch_material_no_loc; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.batch
    ADD CONSTRAINT uq_batch_material_no_loc UNIQUE (material_id, batch_no, location_id);


--
-- Name: location uq_location_triple; Type: CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.location
    ADD CONSTRAINT uq_location_triple UNIQUE (room_no, cabinet_no, layer_no);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: idx_bti_material; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_bti_material ON cost_accounting.bom_template_items USING btree (material_id);


--
-- Name: idx_bti_template; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_bti_template ON cost_accounting.bom_template_items USING btree (template_id);


--
-- Name: idx_materials_category; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_materials_category ON cost_accounting.materials USING btree (category);


--
-- Name: idx_materials_status; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_materials_status ON cost_accounting.materials USING btree (status);


--
-- Name: idx_materials_type; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_materials_type ON cost_accounting.materials USING btree (material_type);


--
-- Name: idx_pbi_material; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_pbi_material ON cost_accounting.project_bom_items USING btree (material_id);


--
-- Name: idx_pbi_project; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_pbi_project ON cost_accounting.project_bom_items USING btree (project_id);


--
-- Name: idx_projects_product; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_projects_product ON cost_accounting.projects USING btree (product_code);


--
-- Name: idx_projects_status; Type: INDEX; Schema: cost_accounting; Owner: -
--

CREATE INDEX idx_projects_status ON cost_accounting.projects USING btree (status);


--
-- Name: ix_attachment_equipment; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_attachment_equipment ON equipment_mgmt.equipment_attachment USING btree (equipment_id);


--
-- Name: ix_calibration_equipment; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_calibration_equipment ON equipment_mgmt.equipment_calibration USING btree (equipment_id, calibration_date DESC);


--
-- Name: ix_calibration_next_date; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_calibration_next_date ON equipment_mgmt.equipment_calibration USING btree (next_calibration_date);


--
-- Name: ix_equipment_category; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_equipment_category ON equipment_mgmt.equipment USING btree (category) WHERE (is_active = true);


--
-- Name: ix_equipment_responsible; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_equipment_responsible ON equipment_mgmt.equipment USING btree (responsible_person);


--
-- Name: ix_equipment_room; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_equipment_room ON equipment_mgmt.equipment USING btree (location_room);


--
-- Name: ix_equipment_status; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_equipment_status ON equipment_mgmt.equipment USING btree (status) WHERE (is_active = true);


--
-- Name: ix_maintenance_equipment; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_maintenance_equipment ON equipment_mgmt.equipment_maintenance USING btree (equipment_id, maintenance_date DESC);


--
-- Name: ix_maintenance_next_date; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_maintenance_next_date ON equipment_mgmt.equipment_maintenance USING btree (next_maintenance_date);


--
-- Name: ix_reminder_due; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_reminder_due ON equipment_mgmt.equipment_reminder USING btree (due_date) WHERE (is_resolved = false);


--
-- Name: ix_reminder_equipment; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_reminder_equipment ON equipment_mgmt.equipment_reminder USING btree (equipment_id);


--
-- Name: ix_repair_equipment; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_repair_equipment ON equipment_mgmt.equipment_repair USING btree (equipment_id, report_date DESC);


--
-- Name: ix_warranty_end; Type: INDEX; Schema: equipment_mgmt; Owner: -
--

CREATE INDEX ix_warranty_end ON equipment_mgmt.equipment_warranty USING btree (warranty_end);


--
-- Name: idx_app_user_active; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_app_user_active ON material_mgmt.app_user USING btree (is_active);


--
-- Name: idx_audit_action_time; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_audit_action_time ON material_mgmt.audit_log USING btree (action, created_at DESC);


--
-- Name: idx_audit_entity_time; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_audit_entity_time ON material_mgmt.audit_log USING btree (entity_type, entity_id, created_at DESC);


--
-- Name: idx_audit_user_time; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_audit_user_time ON material_mgmt.audit_log USING btree (user_id, created_at DESC);


--
-- Name: idx_auth_session_expires; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_auth_session_expires ON material_mgmt.auth_session USING btree (expires_at);


--
-- Name: idx_auth_session_user; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_auth_session_user ON material_mgmt.auth_session USING btree (user_id);


--
-- Name: idx_batch_expiry; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_batch_expiry ON material_mgmt.batch USING btree (expiry_date);


--
-- Name: idx_batch_location; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_batch_location ON material_mgmt.batch USING btree (location_id);


--
-- Name: idx_batch_material; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_batch_material ON material_mgmt.batch USING btree (material_id);


--
-- Name: idx_location_room; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_location_room ON material_mgmt.location USING btree (room_no);


--
-- Name: idx_material_category; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_material_category ON material_mgmt.material USING btree (category);


--
-- Name: idx_material_code; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_material_code ON material_mgmt.material USING btree (material_code);


--
-- Name: idx_material_is_active; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_material_is_active ON material_mgmt.material USING btree (is_active);


--
-- Name: idx_material_name; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_material_name ON material_mgmt.material USING btree (name_cn);


--
-- Name: idx_txn_batch; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_txn_batch ON material_mgmt.inventory_txn USING btree (batch_id);


--
-- Name: idx_txn_date; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_txn_date ON material_mgmt.inventory_txn USING btree (txn_date);


--
-- Name: idx_txn_type; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE INDEX idx_txn_type ON material_mgmt.inventory_txn USING btree (txn_type);


--
-- Name: uq_material_code_non_tt; Type: INDEX; Schema: material_mgmt; Owner: -
--

CREATE UNIQUE INDEX uq_material_code_non_tt ON material_mgmt.material USING btree (material_code) WHERE ((material_code)::text <> 'TT内部物料'::text);


--
-- Name: v_material_usage_stats _RETURN; Type: RULE; Schema: cost_accounting; Owner: -
--

CREATE OR REPLACE VIEW cost_accounting.v_material_usage_stats AS
 SELECT m.id AS material_id,
    m.material_code,
    m.material_name,
    m.material_type,
    m.category,
    m.unit_price,
    m.status,
    count(DISTINCT d.project_id) AS used_in_projects,
    sum(d.cost_amount) AS total_cost_contribution,
    avg(d.cost_amount) AS avg_cost_per_project
   FROM (cost_accounting.materials m
     LEFT JOIN cost_accounting.v_project_cost_detail d ON ((d.material_id = m.id)))
  GROUP BY m.id;


--
-- Name: v_project_summary _RETURN; Type: RULE; Schema: cost_accounting; Owner: -
--

CREATE OR REPLACE VIEW cost_accounting.v_project_summary AS
 SELECT p.id AS project_id,
    p.project_code,
    p.project_name,
    p.product_code,
    p.expression_titer,
    p.culture_volume,
    p.total_yield,
    p.bulk_concentration,
    p.fill_volume_ml,
    ((p.expression_titer * p.culture_volume) * p.total_yield) AS bulk_yield_g,
    COALESCE(sum(d.cost_amount), (0)::numeric) AS total_cost,
    sum(
        CASE
            WHEN ((d.bom_item_id IS NOT NULL) AND (d.cost_amount IS NULL)) THEN 1
            ELSE 0
        END) AS missing_price_rows,
        CASE
            WHEN (((p.expression_titer * p.culture_volume) * p.total_yield) > (0)::numeric) THEN (COALESCE(sum(d.cost_amount), (0)::numeric) / ((p.expression_titer * p.culture_volume) * p.total_yield))
            ELSE NULL::numeric
        END AS cost_per_gram,
        CASE
            WHEN ((((p.expression_titer * p.culture_volume) * p.total_yield) > (0)::numeric) AND (p.bulk_concentration IS NOT NULL) AND (p.fill_volume_ml IS NOT NULL)) THEN ((COALESCE(sum(d.cost_amount), (0)::numeric) / ((p.expression_titer * p.culture_volume) * p.total_yield)) * ((p.fill_volume_ml * p.bulk_concentration) / 1000.0))
            ELSE NULL::numeric
        END AS cost_per_vial,
    p.status,
    p.created_at,
    p.updated_at
   FROM (cost_accounting.projects p
     LEFT JOIN cost_accounting.v_project_cost_detail d ON ((d.project_id = p.id)))
  GROUP BY p.id;


--
-- Name: bom_templates trg_bom_templates_updated_at; Type: TRIGGER; Schema: cost_accounting; Owner: -
--

CREATE TRIGGER trg_bom_templates_updated_at BEFORE UPDATE ON cost_accounting.bom_templates FOR EACH ROW EXECUTE FUNCTION cost_accounting.set_updated_at();


--
-- Name: materials trg_materials_updated_at; Type: TRIGGER; Schema: cost_accounting; Owner: -
--

CREATE TRIGGER trg_materials_updated_at BEFORE UPDATE ON cost_accounting.materials FOR EACH ROW EXECUTE FUNCTION cost_accounting.set_updated_at();


--
-- Name: projects trg_projects_updated_at; Type: TRIGGER; Schema: cost_accounting; Owner: -
--

CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON cost_accounting.projects FOR EACH ROW EXECUTE FUNCTION cost_accounting.set_updated_at();


--
-- Name: equipment equipment_updated_at; Type: TRIGGER; Schema: equipment_mgmt; Owner: -
--

CREATE TRIGGER equipment_updated_at BEFORE UPDATE ON equipment_mgmt.equipment FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();


--
-- Name: equipment_warranty warranty_updated_at; Type: TRIGGER; Schema: equipment_mgmt; Owner: -
--

CREATE TRIGGER warranty_updated_at BEFORE UPDATE ON equipment_mgmt.equipment_warranty FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();


--
-- Name: material material_updated_at; Type: TRIGGER; Schema: material_mgmt; Owner: -
--

CREATE TRIGGER material_updated_at BEFORE UPDATE ON material_mgmt.material FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();


--
-- Name: bom_template_items bom_template_items_material_id_fkey; Type: FK CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_template_items
    ADD CONSTRAINT bom_template_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES cost_accounting.materials(id);


--
-- Name: bom_template_items bom_template_items_template_id_fkey; Type: FK CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.bom_template_items
    ADD CONSTRAINT bom_template_items_template_id_fkey FOREIGN KEY (template_id) REFERENCES cost_accounting.bom_templates(id) ON DELETE CASCADE;


--
-- Name: project_bom_items project_bom_items_material_id_fkey; Type: FK CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.project_bom_items
    ADD CONSTRAINT project_bom_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES cost_accounting.materials(id);


--
-- Name: project_bom_items project_bom_items_project_id_fkey; Type: FK CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.project_bom_items
    ADD CONSTRAINT project_bom_items_project_id_fkey FOREIGN KEY (project_id) REFERENCES cost_accounting.projects(id) ON DELETE CASCADE;


--
-- Name: projects projects_template_id_fkey; Type: FK CONSTRAINT; Schema: cost_accounting; Owner: -
--

ALTER TABLE ONLY cost_accounting.projects
    ADD CONSTRAINT projects_template_id_fkey FOREIGN KEY (template_id) REFERENCES cost_accounting.bom_templates(id);


--
-- Name: equipment_attachment equipment_attachment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_attachment
    ADD CONSTRAINT equipment_attachment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: equipment_calibration equipment_calibration_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_calibration
    ADD CONSTRAINT equipment_calibration_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: equipment_maintenance equipment_maintenance_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: equipment_reminder equipment_reminder_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_reminder
    ADD CONSTRAINT equipment_reminder_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: equipment_repair equipment_repair_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_repair
    ADD CONSTRAINT equipment_repair_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: equipment_warranty equipment_warranty_equipment_id_fkey; Type: FK CONSTRAINT; Schema: equipment_mgmt; Owner: -
--

ALTER TABLE ONLY equipment_mgmt.equipment_warranty
    ADD CONSTRAINT equipment_warranty_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES equipment_mgmt.equipment(equipment_id);


--
-- Name: auth_session auth_session_user_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.auth_session
    ADD CONSTRAINT auth_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES material_mgmt.app_user(id) ON DELETE CASCADE;


--
-- Name: batch batch_location_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.batch
    ADD CONSTRAINT batch_location_id_fkey FOREIGN KEY (location_id) REFERENCES material_mgmt.location(location_id);


--
-- Name: batch batch_material_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.batch
    ADD CONSTRAINT batch_material_id_fkey FOREIGN KEY (material_id) REFERENCES material_mgmt.material(material_id);


--
-- Name: material fk_material_unit; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.material
    ADD CONSTRAINT fk_material_unit FOREIGN KEY (unit) REFERENCES material_mgmt.unit_dict(unit);


--
-- Name: inventory_txn inventory_txn_batch_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.inventory_txn
    ADD CONSTRAINT inventory_txn_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES material_mgmt.batch(batch_id);


--
-- Name: material material_import_batch_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.material
    ADD CONSTRAINT material_import_batch_id_fkey FOREIGN KEY (import_batch_id) REFERENCES material_mgmt.import_log(import_id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 1llZVGJmR0MCbLbq895pPidNez4MU8tb4LQS0Wrj0zPpemClVbBIwjb4jyPpq3m

