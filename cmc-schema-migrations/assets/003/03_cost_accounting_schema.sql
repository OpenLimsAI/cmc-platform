--
-- PostgreSQL database dump
--

\restrict 2nqSKS7AbdU7a8oWmJp5vQ3ERrRFLKfYBZ2XRprhtf6Zefuu0VhKYD7Rvjio6di

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
-- PostgreSQL database dump complete
--

\unrestrict 2nqSKS7AbdU7a8oWmJp5vQ3ERrRFLKfYBZ2XRprhtf6Zefuu0VhKYD7Rvjio6di

