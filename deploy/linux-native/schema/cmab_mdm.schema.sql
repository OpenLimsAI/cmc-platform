--
-- PostgreSQL database dump
--

\restrict d8tfvgTGAO5mkXm0dEDsqJUh2tspmemdLeIgVSB7I7FOBitJppozmeOrQkziYzT

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

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
-- Name: ars; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ars;


--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: meta; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA meta;


--
-- Name: mm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mm;


--
-- Name: prs; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA prs;


--
-- Name: ref; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref;


--
-- Name: srs; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA srs;


--
-- Name: btree_gin; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gin WITH SCHEMA public;


--
-- Name: EXTENSION btree_gin; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gin IS 'support for indexing common datatypes in GIN';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: fn_asset_assign_code(); Type: FUNCTION; Schema: ars; Owner: -
--

CREATE FUNCTION ars.fn_asset_assign_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.asset_code IS NULL OR NEW.asset_code = '' THEN
                NEW.asset_code := meta.fn_next_code('asset');
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_asset_before_update(); Type: FUNCTION; Schema: ars; Owner: -
--

CREATE FUNCTION ars.fn_asset_before_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            -- current_phase 变化时记 phase_change_at
            IF OLD.current_phase IS DISTINCT FROM NEW.current_phase THEN
                NEW.phase_change_at := NOW();
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_asset_status_change(); Type: FUNCTION; Schema: ars; Owner: -
--

CREATE FUNCTION ars.fn_asset_status_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO ars.asset_status_history (
            asset_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.asset_id,
            OLD.status,
            NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: fn_touch_updated_at(); Type: FUNCTION; Schema: ars; Owner: -
--

CREATE FUNCTION ars.fn_touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_audit_trigger(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.fn_audit_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    v_log_id        BIGINT;
    v_user_id       BIGINT;
    v_username      VARCHAR;
    v_session_id    VARCHAR;
    v_request_id    VARCHAR;
    v_ip            INET;
    v_reason        TEXT;
    v_action        VARCHAR;
    v_pk_field      VARCHAR;
    v_code_field    VARCHAR;
    v_parent_ref    VARCHAR;
    v_entity_id     BIGINT;
    v_entity_code   VARCHAR;
    v_old_jsonb     JSONB;
    v_new_jsonb     JSONB;
    v_target_jsonb  JSONB;
    v_field         RECORD;
    v_parent_parts  TEXT[];
    v_parent_schema VARCHAR;
    v_parent_table  VARCHAR;
    v_parent_pk     VARCHAR;
    v_parent_code   VARCHAR;
    v_parent_fk     VARCHAR;
    v_parent_fk_val BIGINT;
BEGIN
    v_user_id    := NULLIF(current_setting('app.user_id',    TRUE), '')::BIGINT;
    v_username   := COALESCE(NULLIF(current_setting('app.username',   TRUE), ''), 'system');
    v_session_id := NULLIF(current_setting('app.session_id', TRUE), '');
    v_request_id := NULLIF(current_setting('app.request_id', TRUE), '');
    v_ip         := NULLIF(current_setting('app.ip_address', TRUE), '')::INET;
    v_reason     := NULLIF(current_setting('app.change_reason', TRUE), '');

    v_pk_field   := TG_ARGV[0];
    v_code_field := NULLIF(TG_ARGV[1], '');
    v_parent_ref := CASE WHEN TG_NARGS >= 3 THEN NULLIF(TG_ARGV[2], '') END;

    IF TG_OP = 'INSERT' THEN
        v_action       := 'CREATE';
        v_new_jsonb    := to_jsonb(NEW);
        v_target_jsonb := v_new_jsonb;
    ELSIF TG_OP = 'UPDATE' THEN
        v_action       := 'UPDATE';
        v_old_jsonb    := to_jsonb(OLD);
        v_new_jsonb    := to_jsonb(NEW);
        v_target_jsonb := v_new_jsonb;
        IF (v_old_jsonb ->> 'deleted_at') IS NULL
           AND (v_new_jsonb ->> 'deleted_at') IS NOT NULL THEN
            v_action := 'DELETE';
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_action       := 'DELETE';
        v_old_jsonb    := to_jsonb(OLD);
        v_target_jsonb := v_old_jsonb;
    END IF;

    v_entity_id := (v_target_jsonb ->> v_pk_field)::BIGINT;

    IF v_code_field IS NOT NULL THEN
        v_entity_code := v_target_jsonb ->> v_code_field;
    END IF;

    -- 子表 entity_code 回溯到父表 code（v2 起；保持不变）
    IF v_entity_code IS NULL AND v_parent_ref IS NOT NULL THEN
        v_parent_parts := string_to_array(v_parent_ref, ':');
        IF array_length(v_parent_parts, 1) = 4 THEN
            v_parent_schema := split_part(v_parent_parts[1], '.', 1);
            v_parent_table  := split_part(v_parent_parts[1], '.', 2);
            v_parent_pk     := v_parent_parts[2];
            v_parent_code   := v_parent_parts[3];
            v_parent_fk     := v_parent_parts[4];
            v_parent_fk_val := (v_target_jsonb ->> v_parent_fk)::BIGINT;
            IF v_parent_fk_val IS NOT NULL THEN
                EXECUTE format(
                    'SELECT %I FROM %I.%I WHERE %I = $1',
                    v_parent_code, v_parent_schema, v_parent_table, v_parent_pk
                ) USING v_parent_fk_val INTO v_entity_code;
            END IF;
        END IF;
    END IF;

    INSERT INTO audit.audit_log (
        user_id, username, session_id, action,
        entity_schema, entity_table, entity_id, entity_code,
        reason, ip_address, request_id, timestamp
    ) VALUES (
        v_user_id, v_username, v_session_id, v_action,
        TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, v_entity_code,
        v_reason, v_ip, v_request_id, NOW()
    ) RETURNING log_id INTO v_log_id;

    -- ============== v3 字段级展开：INSERT / UPDATE / DELETE 全覆盖 ==============
    IF TG_OP = 'INSERT' THEN
        -- 创建：每个非 NULL 字段写一行（old=NULL）；过滤自动维护字段
        FOR v_field IN
            SELECT key,
                   NULL::jsonb AS old_val,
                   v_new_jsonb -> key AS new_val
              FROM jsonb_object_keys(v_new_jsonb) AS key
             WHERE (v_new_jsonb -> key) IS NOT NULL
               AND (v_new_jsonb -> key)::TEXT <> 'null'
               AND key NOT IN ('created_at', 'updated_at', 'updated_by', 'version')
        LOOP
            INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)
            VALUES (v_log_id, v_field.key, v_field.old_val, v_field.new_val);
        END LOOP;

    ELSIF TG_OP = 'UPDATE' THEN
        -- 更新：保持 v2 行为（仅写变化字段）
        FOR v_field IN
            SELECT key,
                   v_old_jsonb -> key AS old_val,
                   v_new_jsonb -> key AS new_val
              FROM jsonb_object_keys(v_new_jsonb) AS key
             WHERE (v_new_jsonb -> key) IS DISTINCT FROM (v_old_jsonb -> key)
               AND key NOT IN ('updated_at', 'updated_by', 'version')
        LOOP
            INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)
            VALUES (v_log_id, v_field.key, v_field.old_val, v_field.new_val);
        END LOOP;

    ELSIF TG_OP = 'DELETE' THEN
        -- 硬删除（极少见）：写完整 OLD 字段（new=NULL）
        FOR v_field IN
            SELECT key,
                   v_old_jsonb -> key AS old_val,
                   NULL::jsonb AS new_val
              FROM jsonb_object_keys(v_old_jsonb) AS key
             WHERE (v_old_jsonb -> key) IS NOT NULL
               AND (v_old_jsonb -> key)::TEXT <> 'null'
               AND key NOT IN ('created_at', 'updated_at', 'updated_by', 'version')
        LOOP
            INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)
            VALUES (v_log_id, v_field.key, v_field.old_val, v_field.new_val);
        END LOOP;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$_$;


--
-- Name: FUNCTION fn_audit_trigger(); Type: COMMENT; Schema: audit; Owner: -
--

COMMENT ON FUNCTION audit.fn_audit_trigger() IS '通用审计触发器，业务表挂 AFTER INSERT/UPDATE/DELETE 即接入';


--
-- Name: fn_ensure_year_sequence(character varying, character varying, integer, integer); Type: FUNCTION; Schema: meta; Owner: -
--

CREATE FUNCTION meta.fn_ensure_year_sequence(p_kind character varying, p_prefix character varying, p_year integer, p_padding integer) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_seq_name VARCHAR;
        BEGIN
            v_seq_name := p_kind || '_' || p_year::text;
            INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
            VALUES (
                v_seq_name,
                p_prefix || p_year::text || '-',
                p_padding,
                'Year-scoped sequence for ' || p_kind || ' in ' || p_year::text
            )
            ON CONFLICT (sequence_name) DO NOTHING;
            RETURN v_seq_name;
        END;
        $$;


--
-- Name: fn_next_code(character varying); Type: FUNCTION; Schema: meta; Owner: -
--

CREATE FUNCTION meta.fn_next_code(p_sequence_name character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_prefix   VARCHAR;
            v_value    BIGINT;
            v_padding  INT;
        BEGIN
            UPDATE meta.code_sequence
               SET current_value = current_value + increment_step,
                   updated_at    = NOW()
             WHERE sequence_name = p_sequence_name
            RETURNING prefix, current_value, padding_length
                INTO v_prefix, v_value, v_padding;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Code sequence % not found', p_sequence_name;
            END IF;

            RETURN v_prefix || LPAD(v_value::text, v_padding, '0');
        END;
        $$;


--
-- Name: fn_material_assign_code(); Type: FUNCTION; Schema: mm; Owner: -
--

CREATE FUNCTION mm.fn_material_assign_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.material_code IS NULL OR NEW.material_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('material', 'MAT-', v_year, 6);
                NEW.material_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_material_batch_before_update(); Type: FUNCTION; Schema: mm; Owner: -
--

CREATE FUNCTION mm.fn_material_batch_before_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_material_before_update(); Type: FUNCTION; Schema: mm; Owner: -
--

CREATE FUNCTION mm.fn_material_before_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_project_assign_code(); Type: FUNCTION; Schema: prs; Owner: -
--

CREATE FUNCTION prs.fn_project_assign_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('project', 'PRJ-', v_year, 4);
                NEW.project_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_project_before_update(); Type: FUNCTION; Schema: prs; Owner: -
--

CREATE FUNCTION prs.fn_project_before_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_project_status_change(); Type: FUNCTION; Schema: prs; Owner: -
--

CREATE FUNCTION prs.fn_project_status_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO prs.project_status_history (
            project_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.project_id,
            OLD.status,
            NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: fn_touch_updated_at(); Type: FUNCTION; Schema: prs; Owner: -
--

CREATE FUNCTION prs.fn_touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_substance_assign_code(); Type: FUNCTION; Schema: srs; Owner: -
--

CREATE FUNCTION srs.fn_substance_assign_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.substance_code IS NULL OR NEW.substance_code = '' THEN
                NEW.substance_code := meta.fn_next_code('substance');
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_substance_before_update(); Type: FUNCTION; Schema: srs; Owner: -
--

CREATE FUNCTION srs.fn_substance_before_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_substance_protein_compute_hash(); Type: FUNCTION; Schema: srs; Owner: -
--

CREATE FUNCTION srs.fn_substance_protein_compute_hash() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.heavy_chain_sequence IS NOT NULL AND NEW.heavy_chain_sequence <> '' THEN
                NEW.sequence_hash_hc := encode(
                    digest(regexp_replace(UPPER(NEW.heavy_chain_sequence), '[^A-Z]', '', 'g'),
                           'sha256'),
                    'hex'
                );
                NEW.sequence_length_hc := length(
                    regexp_replace(UPPER(NEW.heavy_chain_sequence), '[^A-Z]', '', 'g')
                );
            ELSE
                NEW.sequence_hash_hc   := NULL;
                NEW.sequence_length_hc := NULL;
            END IF;
            IF NEW.light_chain_sequence IS NOT NULL AND NEW.light_chain_sequence <> '' THEN
                NEW.sequence_hash_lc := encode(
                    digest(regexp_replace(UPPER(NEW.light_chain_sequence), '[^A-Z]', '', 'g'),
                           'sha256'),
                    'hex'
                );
                NEW.sequence_length_lc := length(
                    regexp_replace(UPPER(NEW.light_chain_sequence), '[^A-Z]', '', 'g')
                );
            ELSE
                NEW.sequence_hash_lc   := NULL;
                NEW.sequence_length_lc := NULL;
            END IF;
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: fn_substance_status_change(); Type: FUNCTION; Schema: srs; Owner: -
--

CREATE FUNCTION srs.fn_substance_status_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO srs.substance_status_history (
            substance_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.substance_id,
            OLD.status,
            NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: fn_touch_updated_at(); Type: FUNCTION; Schema: srs; Owner: -
--

CREATE FUNCTION srs.fn_touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: asset; Type: TABLE; Schema: ars; Owner: -
--

CREATE TABLE ars.asset (
    asset_id bigint NOT NULL,
    asset_code character varying(32) NOT NULL,
    internal_name character varying(255) NOT NULL,
    trade_name character varying(255),
    inn_name character varying(255),
    asset_type character varying(32) NOT NULL,
    therapeutic_area character varying(64),
    indication text,
    dosage_form character varying(64),
    strength character varying(64),
    route_of_administration character varying(32),
    current_phase character varying(32) DEFAULT 'discovery'::character varying NOT NULL,
    phase_change_at timestamp with time zone,
    status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    is_commercial boolean DEFAULT false NOT NULL,
    first_approval_date date,
    first_launch_date date,
    description text,
    notes text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    version integer DEFAULT 1 NOT NULL,
    CONSTRAINT ck_asset_ck_asset_phase CHECK (((current_phase)::text = ANY ((ARRAY['discovery'::character varying, 'preclinical'::character varying, 'phase_1'::character varying, 'phase_2'::character varying, 'phase_3'::character varying, 'submission'::character varying, 'approved'::character varying, 'marketed'::character varying, 'discontinued'::character varying])::text[]))),
    CONSTRAINT ck_asset_ck_asset_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'on_hold'::character varying, 'terminated'::character varying])::text[]))),
    CONSTRAINT ck_asset_ck_asset_type CHECK (((asset_type)::text = ANY ((ARRAY['mab'::character varying, 'bispecific'::character varying, 'adc'::character varying, 'fusion'::character varying, 'small_molecule'::character varying, 'combination'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: asset_asset_id_seq; Type: SEQUENCE; Schema: ars; Owner: -
--

ALTER TABLE ars.asset ALTER COLUMN asset_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ars.asset_asset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: asset_market_id; Type: TABLE; Schema: ars; Owner: -
--

CREATE TABLE ars.asset_market_id (
    market_id_pk bigint NOT NULL,
    asset_id bigint NOT NULL,
    market_code character varying(8) NOT NULL,
    id_type character varying(32) NOT NULL,
    id_value character varying(128) NOT NULL,
    issuing_authority character varying(128),
    application_date date,
    approval_date date,
    expiry_date date,
    status character varying(32),
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint
);


--
-- Name: asset_market_id_market_id_pk_seq; Type: SEQUENCE; Schema: ars; Owner: -
--

ALTER TABLE ars.asset_market_id ALTER COLUMN market_id_pk ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ars.asset_market_id_market_id_pk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: asset_status_history; Type: TABLE; Schema: ars; Owner: -
--

CREATE TABLE ars.asset_status_history (
    history_id bigint NOT NULL,
    asset_id bigint NOT NULL,
    old_status character varying(32),
    new_status character varying(32) NOT NULL,
    change_reason text NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by bigint NOT NULL,
    e_signature_id bigint
);


--
-- Name: asset_status_history_history_id_seq; Type: SEQUENCE; Schema: ars; Owner: -
--

ALTER TABLE ars.asset_status_history ALTER COLUMN history_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME ars.asset_status_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_log; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.audit_log (
    log_id bigint NOT NULL,
    user_id bigint,
    username character varying(64) NOT NULL,
    session_id character varying(64),
    action character varying(32) NOT NULL,
    entity_schema character varying(32),
    entity_table character varying(64),
    entity_id bigint,
    entity_code character varying(64),
    change_summary text,
    reason text,
    ip_address inet,
    user_agent text,
    request_id character varying(64),
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    extra jsonb,
    CONSTRAINT ck_audit_log_ck_audit_log_action CHECK (((action)::text = ANY ((ARRAY['CREATE'::character varying, 'READ'::character varying, 'UPDATE'::character varying, 'DELETE'::character varying, 'RESTORE'::character varying, 'APPROVE'::character varying, 'REJECT'::character varying, 'SIGN'::character varying, 'LOGIN'::character varying, 'LOGOUT'::character varying, 'LOGIN_FAILED'::character varying, 'EXPORT'::character varying, 'IMPORT'::character varying, 'PERMISSION_CHANGE'::character varying])::text[])))
);


--
-- Name: audit_log_log_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

ALTER TABLE audit.audit_log ALTER COLUMN log_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME audit.audit_log_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: change_history; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.change_history (
    history_id bigint NOT NULL,
    audit_log_id bigint NOT NULL,
    field_name character varying(64) NOT NULL,
    old_value jsonb,
    new_value jsonb
);


--
-- Name: change_history_history_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

ALTER TABLE audit.change_history ALTER COLUMN history_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME audit.change_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: e_signature; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.e_signature (
    signature_id bigint NOT NULL,
    user_id bigint NOT NULL,
    username character varying(64) NOT NULL,
    full_name character varying(128) NOT NULL,
    entity_schema character varying(32) NOT NULL,
    entity_table character varying(64) NOT NULL,
    entity_id bigint NOT NULL,
    entity_code character varying(64),
    signature_meaning character varying(64) NOT NULL,
    signature_reason text NOT NULL,
    signed_content_hash character varying(64) NOT NULL,
    signature_hash character varying(64) NOT NULL,
    ip_address inet,
    user_agent text,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    audit_log_id bigint,
    CONSTRAINT ck_e_signature_ck_e_signature_meaning CHECK (((signature_meaning)::text = ANY ((ARRAY['approve'::character varying, 'review'::character varying, 'release'::character varying, 'witness'::character varying, 'reject'::character varying])::text[])))
);


--
-- Name: e_signature_signature_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

ALTER TABLE audit.e_signature ALTER COLUMN signature_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME audit.e_signature_signature_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: login_history; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.login_history (
    login_id bigint NOT NULL,
    user_id bigint,
    username_input character varying(64) NOT NULL,
    success boolean NOT NULL,
    failure_reason character varying(64),
    ip_address character varying(45),
    user_agent text,
    login_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: login_history_login_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

ALTER TABLE auth.login_history ALTER COLUMN login_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME auth.login_history_login_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: permission; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.permission (
    permission_id bigint NOT NULL,
    permission_code character varying(64) NOT NULL,
    resource character varying(64) NOT NULL,
    action character varying(32) NOT NULL,
    description text,
    is_system boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: permission_permission_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

ALTER TABLE auth.permission ALTER COLUMN permission_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME auth.permission_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: refresh_token; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.refresh_token (
    jti character varying(36) NOT NULL,
    user_id bigint NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revoked_reason character varying(32),
    rotated_to_jti character varying(36),
    ip_address character varying(45),
    user_agent character varying(512),
    CONSTRAINT ck_refresh_token_ck_refresh_token_reason CHECK (((revoked_reason IS NULL) OR ((revoked_reason)::text = ANY ((ARRAY['rotated'::character varying, 'logout'::character varying, 'password_changed'::character varying, 'admin'::character varying, 'expired'::character varying])::text[]))))
);


--
-- Name: role; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.role (
    role_id bigint NOT NULL,
    role_code character varying(32) NOT NULL,
    role_name character varying(64) NOT NULL,
    description text,
    is_system boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint,
    deleted_at timestamp with time zone,
    deleted_by bigint
);


--
-- Name: role_permission; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.role_permission (
    role_id bigint NOT NULL,
    permission_id bigint NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    granted_by bigint
);


--
-- Name: role_role_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

ALTER TABLE auth.role ALTER COLUMN role_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME auth.role_role_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: user; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth."user" (
    user_id bigint NOT NULL,
    username character varying(64) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(128) NOT NULL,
    full_name_en character varying(128),
    department character varying(64),
    title character varying(64),
    phone character varying(32),
    status character varying(16) DEFAULT 'active'::character varying NOT NULL,
    failed_login_count integer DEFAULT 0 NOT NULL,
    last_login_at timestamp with time zone,
    password_changed_at timestamp with time zone,
    password_expires_at timestamp with time zone,
    mfa_enabled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    locked_at timestamp with time zone,
    force_password_change boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_user_ck_user_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'locked'::character varying, 'disabled'::character varying])::text[])))
);


--
-- Name: user_role; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.user_role (
    user_id bigint NOT NULL,
    role_id bigint NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    granted_by bigint,
    expires_at timestamp with time zone
);


--
-- Name: user_user_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

ALTER TABLE auth."user" ALTER COLUMN user_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME auth.user_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: code_sequence; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.code_sequence (
    sequence_id bigint NOT NULL,
    sequence_name character varying(64) NOT NULL,
    prefix character varying(16) NOT NULL,
    current_value bigint DEFAULT '0'::bigint NOT NULL,
    padding_length integer DEFAULT 7 NOT NULL,
    increment_step integer DEFAULT 1 NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: code_sequence_sequence_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

ALTER TABLE meta.code_sequence ALTER COLUMN sequence_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME meta.code_sequence_sequence_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: lookup_value; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.lookup_value (
    lookup_id bigint NOT NULL,
    lookup_type character varying(64) NOT NULL,
    lookup_code character varying(64) NOT NULL,
    lookup_name character varying(128) NOT NULL,
    lookup_name_en character varying(128),
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    description text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lookup_value_lookup_id_seq; Type: SEQUENCE; Schema: meta; Owner: -
--

ALTER TABLE meta.lookup_value ALTER COLUMN lookup_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME meta.lookup_value_lookup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: system_config; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.system_config (
    config_key character varying(64) NOT NULL,
    config_value text NOT NULL,
    value_type character varying(16) DEFAULT 'string'::character varying NOT NULL,
    description text,
    is_sensitive boolean DEFAULT false NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint,
    CONSTRAINT ck_system_config_ck_config_type CHECK (((value_type)::text = ANY ((ARRAY['string'::character varying, 'int'::character varying, 'bool'::character varying, 'json'::character varying])::text[])))
);


--
-- Name: material; Type: TABLE; Schema: mm; Owner: -
--

CREATE TABLE mm.material (
    material_id bigint NOT NULL,
    material_code character varying(32) NOT NULL,
    material_name character varying(255) NOT NULL,
    material_name_en character varying(255),
    material_type character varying(32) NOT NULL,
    substance_id bigint,
    physical_form character varying(64),
    storage_condition character varying(64),
    source_type character varying(32),
    source_name character varying(128),
    grade character varying(32),
    status character varying(32) DEFAULT 'active'::character varying NOT NULL,
    description text,
    notes text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    manufacturer character varying(100),
    catalog_no character varying(100),
    spec_model character varying(200),
    unit character varying(20) DEFAULT 'ea'::character varying NOT NULL,
    package_spec character varying(100),
    hazard_class text[],
    category character varying(50),
    CONSTRAINT ck_material_category CHECK (((category IS NULL) OR ((category)::text = ANY ((ARRAY['一般耗材'::character varying, '关键耗材'::character varying, '关键试剂'::character varying, '内包材'::character varying, '外包材'::character varying, '劳保'::character varying, '原辅料'::character varying, '参比品'::character varying, '对照品'::character varying, '工艺用水/气'::character varying, '标准品'::character varying, '细胞种子'::character varying, '自制包材'::character varying, '试剂'::character varying, '运输包装材料'::character varying])::text[])))),
    CONSTRAINT ck_material_ck_material_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'quarantine'::character varying, 'released'::character varying, 'rejected'::character varying, 'retired'::character varying])::text[]))),
    CONSTRAINT ck_material_type CHECK (((material_type)::text = ANY ((ARRAY['reagent'::character varying, 'consumable'::character varying, 'standard'::character varying, 'column'::character varying])::text[])))
);


--
-- Name: material_batch; Type: TABLE; Schema: mm; Owner: -
--

CREATE TABLE mm.material_batch (
    batch_id bigint NOT NULL,
    material_id bigint NOT NULL,
    batch_number character varying(64) NOT NULL,
    quantity_value numeric(18,4),
    quantity_unit character varying(16),
    manufacture_date date,
    expiry_date date,
    receive_date date,
    status character varying(32) DEFAULT 'in_stock'::character varying NOT NULL,
    source_batch_ref character varying(128),
    coa_url text,
    storage_location character varying(128),
    notes text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    CONSTRAINT ck_material_batch_ck_material_batch_status CHECK (((status)::text = ANY ((ARRAY['in_stock'::character varying, 'in_use'::character varying, 'depleted'::character varying, 'expired'::character varying, 'recalled'::character varying])::text[])))
);


--
-- Name: material_batch_batch_id_seq; Type: SEQUENCE; Schema: mm; Owner: -
--

ALTER TABLE mm.material_batch ALTER COLUMN batch_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME mm.material_batch_batch_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: material_material_id_seq; Type: SEQUENCE; Schema: mm; Owner: -
--

ALTER TABLE mm.material ALTER COLUMN material_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME mm.material_material_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project; Type: TABLE; Schema: prs; Owner: -
--

CREATE TABLE prs.project (
    project_id bigint NOT NULL,
    project_code character varying(32) NOT NULL,
    project_name character varying(255) NOT NULL,
    project_name_en character varying(255),
    project_type character varying(32) NOT NULL,
    project_phase character varying(32),
    therapeutic_area character varying(128),
    indication character varying(255),
    planned_start_date date,
    planned_end_date date,
    actual_start_date date,
    actual_end_date date,
    status character varying(32) DEFAULT 'proposed'::character varying NOT NULL,
    project_manager_id bigint,
    program_director_id bigint,
    description text,
    notes text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    version integer DEFAULT 1 NOT NULL,
    parent_project_id bigint,
    program_name character varying(128),
    sponsor_id bigint,
    department character varying(64),
    budget_total numeric(18,2),
    budget_currency character varying(8) DEFAULT 'CNY'::character varying,
    budget_actual numeric(18,2),
    objective text,
    scope text,
    deliverables text,
    success_criteria text,
    priority character varying(16),
    confidentiality character varying(16) DEFAULT 'internal'::character varying NOT NULL,
    CONSTRAINT ck_project_ck_project_dates CHECK (((planned_end_date IS NULL) OR (planned_start_date IS NULL) OR (planned_end_date >= planned_start_date))),
    CONSTRAINT ck_project_ck_project_status CHECK (((status)::text = ANY ((ARRAY['proposed'::character varying, 'initiated'::character varying, 'active'::character varying, 'on_hold'::character varying, 'completed'::character varying, 'terminated'::character varying])::text[]))),
    CONSTRAINT ck_project_ck_project_type CHECK (((project_type)::text = ANY ((ARRAY['cmc'::character varying, 'preclinical'::character varying, 'clinical'::character varying, 'regulatory'::character varying, 'commercial'::character varying, 'platform'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: project_milestone; Type: TABLE; Schema: prs; Owner: -
--

CREATE TABLE prs.project_milestone (
    milestone_id bigint NOT NULL,
    project_id bigint NOT NULL,
    milestone_name character varying(255) NOT NULL,
    milestone_type character varying(32) NOT NULL,
    planned_date date NOT NULL,
    actual_date date,
    status character varying(16) DEFAULT 'planned'::character varying NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    CONSTRAINT ck_project_milestone_ck_project_milestone_status CHECK (((status)::text = ANY ((ARRAY['planned'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'delayed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT ck_project_milestone_ck_project_milestone_type CHECK (((milestone_type)::text = ANY ((ARRAY['gate'::character varying, 'deliverable'::character varying, 'decision'::character varying])::text[])))
);


--
-- Name: project_milestone_milestone_id_seq; Type: SEQUENCE; Schema: prs; Owner: -
--

ALTER TABLE prs.project_milestone ALTER COLUMN milestone_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME prs.project_milestone_milestone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_project_id_seq; Type: SEQUENCE; Schema: prs; Owner: -
--

ALTER TABLE prs.project ALTER COLUMN project_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME prs.project_project_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_relationship; Type: TABLE; Schema: prs; Owner: -
--

CREATE TABLE prs.project_relationship (
    relationship_id bigint NOT NULL,
    from_project_id bigint NOT NULL,
    to_project_id bigint NOT NULL,
    relationship_type character varying(32) NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    CONSTRAINT ck_project_relationship_ck_project_rel_self CHECK ((from_project_id <> to_project_id)),
    CONSTRAINT ck_project_relationship_ck_project_rel_type CHECK (((relationship_type)::text = ANY ((ARRAY['merged_into'::character varying, 'split_from'::character varying, 'derived_from'::character varying, 'depends_on'::character varying, 'blocks'::character varying])::text[])))
);


--
-- Name: project_relationship_relationship_id_seq; Type: SEQUENCE; Schema: prs; Owner: -
--

ALTER TABLE prs.project_relationship ALTER COLUMN relationship_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME prs.project_relationship_relationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_status_history; Type: TABLE; Schema: prs; Owner: -
--

CREATE TABLE prs.project_status_history (
    history_id bigint NOT NULL,
    project_id bigint NOT NULL,
    old_status character varying(32),
    new_status character varying(32) NOT NULL,
    change_reason text NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by bigint NOT NULL,
    e_signature_id bigint
);


--
-- Name: project_status_history_history_id_seq; Type: SEQUENCE; Schema: prs; Owner: -
--

ALTER TABLE prs.project_status_history ALTER COLUMN history_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME prs.project_status_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_team; Type: TABLE; Schema: prs; Owner: -
--

CREATE TABLE prs.project_team (
    team_id bigint NOT NULL,
    project_id bigint NOT NULL,
    user_id bigint NOT NULL,
    role character varying(32) NOT NULL,
    joined_at date DEFAULT CURRENT_DATE NOT NULL,
    left_at date,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    function_area character varying(64),
    allocation_pct integer,
    CONSTRAINT ck_project_team_ck_project_team_alloc CHECK (((allocation_pct IS NULL) OR ((allocation_pct >= 0) AND (allocation_pct <= 100))))
);


--
-- Name: project_team_team_id_seq; Type: SEQUENCE; Schema: prs; Owner: -
--

ALTER TABLE prs.project_team ALTER COLUMN team_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME prs.project_team_team_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: asset_substance; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.asset_substance (
    asset_id bigint NOT NULL,
    substance_id bigint NOT NULL,
    component_role character varying(32) NOT NULL,
    is_active_ingredient boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    CONSTRAINT ck_asset_substance_ck_ref_as_role CHECK (((component_role)::text = ANY ((ARRAY['main_component'::character varying, 'antibody'::character varying, 'linker'::character varying, 'payload'::character varying, 'excipient'::character varying, 'impurity'::character varying])::text[])))
);


--
-- Name: project_asset; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.project_asset (
    project_id bigint NOT NULL,
    asset_id bigint NOT NULL,
    relation_type character varying(32) DEFAULT 'primary'::character varying NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint
);


--
-- Name: project_substance; Type: TABLE; Schema: ref; Owner: -
--

CREATE TABLE ref.project_substance (
    project_id bigint NOT NULL,
    substance_id bigint NOT NULL,
    relation_type character varying(32) DEFAULT 'primary'::character varying NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    CONSTRAINT ck_project_substance_ck_ref_ps_type CHECK (((relation_type)::text = ANY ((ARRAY['primary'::character varying, 'secondary'::character varying, 'reference'::character varying, 'control'::character varying, 'derivative'::character varying])::text[])))
);


--
-- Name: substance; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance (
    substance_id bigint NOT NULL,
    substance_code character varying(32) NOT NULL,
    substance_type character varying(32) NOT NULL,
    internal_code character varying(64),
    preferred_name character varying(255) NOT NULL,
    preferred_name_en character varying(255),
    display_name character varying(255),
    target character varying(128),
    target_type character varying(64),
    modality character varying(64),
    status character varying(32) DEFAULT 'draft'::character varying NOT NULL,
    is_proprietary boolean DEFAULT true NOT NULL,
    confidentiality character varying(16) DEFAULT 'internal'::character varying NOT NULL,
    external_uuid uuid DEFAULT gen_random_uuid(),
    description text,
    notes text,
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    registered_at timestamp with time zone,
    registered_by bigint,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    version integer DEFAULT 1 NOT NULL,
    CONSTRAINT ck_substance_ck_substance_confidentiality CHECK (((confidentiality)::text = ANY ((ARRAY['public'::character varying, 'internal'::character varying, 'restricted'::character varying])::text[]))),
    CONSTRAINT ck_substance_ck_substance_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'registered'::character varying, 'active'::character varying, 'restricted'::character varying, 'deprecated'::character varying, 'obsoleted'::character varying])::text[]))),
    CONSTRAINT ck_substance_ck_substance_substance_type CHECK (((substance_type)::text = ANY ((ARRAY['mab'::character varying, 'bispecific'::character varying, 'adc'::character varying, 'fusion'::character varying, 'small_molecule'::character varying, 'oligonucleotide'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: substance_adc; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_adc (
    substance_id bigint NOT NULL,
    antibody_substance_id bigint NOT NULL,
    linker_substance_id bigint,
    payload_substance_id bigint NOT NULL,
    dar_average numeric(4,2),
    dar_distribution jsonb,
    dar_method character varying(64),
    conjugation_chemistry character varying(64),
    conjugation_site character varying(128),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_substance_adc_ck_substance_adc_dar CHECK (((dar_average IS NULL) OR ((dar_average >= (0)::numeric) AND (dar_average <= (30)::numeric))))
);


--
-- Name: substance_alias; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_alias (
    alias_id bigint NOT NULL,
    substance_id bigint NOT NULL,
    alias_value character varying(255) NOT NULL,
    alias_type character varying(32),
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: substance_alias_alias_id_seq; Type: SEQUENCE; Schema: srs; Owner: -
--

ALTER TABLE srs.substance_alias ALTER COLUMN alias_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME srs.substance_alias_alias_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: substance_protein; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_protein (
    substance_id bigint NOT NULL,
    heavy_chain_sequence text,
    light_chain_sequence text,
    additional_chains jsonb,
    sequence_length_hc integer,
    sequence_length_lc integer,
    sequence_hash_hc character varying(64),
    sequence_hash_lc character varying(64),
    isotype character varying(32),
    architecture character varying(64),
    disulfide_bonds jsonb,
    glycosylation_sites jsonb,
    ptm_info jsonb,
    expression_system character varying(64),
    cell_line character varying(128),
    expression_vector character varying(128),
    molecular_weight_da double precision,
    pi_theoretical double precision,
    extinction_coefficient double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: substance_small_molecule; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_small_molecule (
    substance_id bigint NOT NULL,
    smiles text,
    inchi text,
    inchi_key character varying(27),
    molecular_formula character varying(64),
    molecular_weight numeric(10,4),
    salt_form character varying(64),
    crystal_form character varying(64),
    stereochemistry character varying(64),
    extra jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: substance_status_history; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_status_history (
    history_id bigint NOT NULL,
    substance_id bigint NOT NULL,
    old_status character varying(32),
    new_status character varying(32) NOT NULL,
    change_reason text NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by bigint NOT NULL,
    e_signature_id bigint,
    merged_to_substance_id bigint
);


--
-- Name: substance_status_history_history_id_seq; Type: SEQUENCE; Schema: srs; Owner: -
--

ALTER TABLE srs.substance_status_history ALTER COLUMN history_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME srs.substance_status_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: substance_substance_id_seq; Type: SEQUENCE; Schema: srs; Owner: -
--

ALTER TABLE srs.substance ALTER COLUMN substance_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME srs.substance_substance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: substance_xref; Type: TABLE; Schema: srs; Owner: -
--

CREATE TABLE srs.substance_xref (
    xref_id bigint NOT NULL,
    substance_id bigint NOT NULL,
    xref_type character varying(32) NOT NULL,
    xref_value character varying(255) NOT NULL,
    xref_source character varying(64),
    region character varying(16),
    is_primary boolean DEFAULT false NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by bigint NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by bigint NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    effective_date date,
    expiry_date date,
    CONSTRAINT ck_substance_xref_ck_substance_xref_xref_type CHECK (((xref_type)::text = ANY ((ARRAY['INN'::character varying, 'USAN'::character varying, 'CAS'::character varying, 'UNII'::character varying, 'GSRS_UUID'::character varying, 'ChEMBL'::character varying, 'DRUGBANK'::character varying, 'TRADE_NAME'::character varying, 'GENERIC_NAME'::character varying, 'HISTORICAL_CODE'::character varying, 'PROJECT_CODE'::character varying, 'OTHER'::character varying])::text[])))
);


--
-- Name: substance_xref_xref_id_seq; Type: SEQUENCE; Schema: srs; Owner: -
--

ALTER TABLE srs.substance_xref ALTER COLUMN xref_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME srs.substance_xref_xref_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: asset pk_asset; Type: CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset
    ADD CONSTRAINT pk_asset PRIMARY KEY (asset_id);


--
-- Name: asset_market_id pk_asset_market_id; Type: CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT pk_asset_market_id PRIMARY KEY (market_id_pk);


--
-- Name: asset_status_history pk_asset_status_history; Type: CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_status_history
    ADD CONSTRAINT pk_asset_status_history PRIMARY KEY (history_id);


--
-- Name: asset uq_asset_code; Type: CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset
    ADD CONSTRAINT uq_asset_code UNIQUE (asset_code);


--
-- Name: asset_market_id uq_asset_market_id; Type: CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT uq_asset_market_id UNIQUE (asset_id, market_code, id_type, id_value);


--
-- Name: audit_log pk_audit_log; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.audit_log
    ADD CONSTRAINT pk_audit_log PRIMARY KEY (log_id);


--
-- Name: change_history pk_change_history; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.change_history
    ADD CONSTRAINT pk_change_history PRIMARY KEY (history_id);


--
-- Name: e_signature pk_e_signature; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.e_signature
    ADD CONSTRAINT pk_e_signature PRIMARY KEY (signature_id);


--
-- Name: login_history pk_login_history; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.login_history
    ADD CONSTRAINT pk_login_history PRIMARY KEY (login_id);


--
-- Name: permission pk_permission; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permission
    ADD CONSTRAINT pk_permission PRIMARY KEY (permission_id);


--
-- Name: refresh_token pk_refresh_token; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_token
    ADD CONSTRAINT pk_refresh_token PRIMARY KEY (jti);


--
-- Name: role pk_role; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role
    ADD CONSTRAINT pk_role PRIMARY KEY (role_id);


--
-- Name: role_permission pk_role_permission; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permission
    ADD CONSTRAINT pk_role_permission PRIMARY KEY (role_id, permission_id);


--
-- Name: user pk_user; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth."user"
    ADD CONSTRAINT pk_user PRIMARY KEY (user_id);


--
-- Name: user_role pk_user_role; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_role
    ADD CONSTRAINT pk_user_role PRIMARY KEY (user_id, role_id);


--
-- Name: permission uq_permission_permission_code; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permission
    ADD CONSTRAINT uq_permission_permission_code UNIQUE (permission_code);


--
-- Name: permission uq_permission_resource_action; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.permission
    ADD CONSTRAINT uq_permission_resource_action UNIQUE (resource, action);


--
-- Name: role uq_role_role_code; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role
    ADD CONSTRAINT uq_role_role_code UNIQUE (role_code);


--
-- Name: user uq_user_email; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth."user"
    ADD CONSTRAINT uq_user_email UNIQUE (email);


--
-- Name: user uq_user_username; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth."user"
    ADD CONSTRAINT uq_user_username UNIQUE (username);


--
-- Name: code_sequence pk_code_sequence; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.code_sequence
    ADD CONSTRAINT pk_code_sequence PRIMARY KEY (sequence_id);


--
-- Name: lookup_value pk_lookup_value; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.lookup_value
    ADD CONSTRAINT pk_lookup_value PRIMARY KEY (lookup_id);


--
-- Name: system_config pk_system_config; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.system_config
    ADD CONSTRAINT pk_system_config PRIMARY KEY (config_key);


--
-- Name: code_sequence uq_code_sequence_sequence_name; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.code_sequence
    ADD CONSTRAINT uq_code_sequence_sequence_name UNIQUE (sequence_name);


--
-- Name: lookup_value uq_lookup_type_code; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.lookup_value
    ADD CONSTRAINT uq_lookup_type_code UNIQUE (lookup_type, lookup_code);


--
-- Name: material pk_material; Type: CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT pk_material PRIMARY KEY (material_id);


--
-- Name: material_batch pk_material_batch; Type: CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT pk_material_batch PRIMARY KEY (batch_id);


--
-- Name: material_batch uq_material_batch; Type: CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT uq_material_batch UNIQUE (material_id, batch_number);


--
-- Name: material uq_material_code; Type: CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT uq_material_code UNIQUE (material_code);


--
-- Name: project pk_project; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT pk_project PRIMARY KEY (project_id);


--
-- Name: project_milestone pk_project_milestone; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_milestone
    ADD CONSTRAINT pk_project_milestone PRIMARY KEY (milestone_id);


--
-- Name: project_relationship pk_project_relationship; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_relationship
    ADD CONSTRAINT pk_project_relationship PRIMARY KEY (relationship_id);


--
-- Name: project_status_history pk_project_status_history; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_status_history
    ADD CONSTRAINT pk_project_status_history PRIMARY KEY (history_id);


--
-- Name: project_team pk_project_team; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_team
    ADD CONSTRAINT pk_project_team PRIMARY KEY (team_id);


--
-- Name: project uq_project_project_code; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT uq_project_project_code UNIQUE (project_code);


--
-- Name: project_relationship uq_project_relationship; Type: CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_relationship
    ADD CONSTRAINT uq_project_relationship UNIQUE (from_project_id, to_project_id, relationship_type);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: asset_substance pk_ref_asset_substance; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT pk_ref_asset_substance PRIMARY KEY (asset_id, substance_id, component_role);


--
-- Name: project_asset pk_ref_project_asset; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT pk_ref_project_asset PRIMARY KEY (project_id, asset_id);


--
-- Name: project_substance pk_ref_project_substance; Type: CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT pk_ref_project_substance PRIMARY KEY (project_id, substance_id, relation_type);


--
-- Name: substance pk_substance; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT pk_substance PRIMARY KEY (substance_id);


--
-- Name: substance_adc pk_substance_adc; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_adc
    ADD CONSTRAINT pk_substance_adc PRIMARY KEY (substance_id);


--
-- Name: substance_alias pk_substance_alias; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_alias
    ADD CONSTRAINT pk_substance_alias PRIMARY KEY (alias_id);


--
-- Name: substance_protein pk_substance_protein; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_protein
    ADD CONSTRAINT pk_substance_protein PRIMARY KEY (substance_id);


--
-- Name: substance_small_molecule pk_substance_small_molecule; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_small_molecule
    ADD CONSTRAINT pk_substance_small_molecule PRIMARY KEY (substance_id);


--
-- Name: substance_status_history pk_substance_status_history; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_status_history
    ADD CONSTRAINT pk_substance_status_history PRIMARY KEY (history_id);


--
-- Name: substance_xref pk_substance_xref; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_xref
    ADD CONSTRAINT pk_substance_xref PRIMARY KEY (xref_id);


--
-- Name: substance uq_substance_external_uuid; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT uq_substance_external_uuid UNIQUE (external_uuid);


--
-- Name: substance uq_substance_internal_code; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT uq_substance_internal_code UNIQUE (internal_code);


--
-- Name: substance uq_substance_substance_code; Type: CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT uq_substance_substance_code UNIQUE (substance_code);


--
-- Name: ix_asset_market_id_asset; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_market_id_asset ON ars.asset_market_id USING btree (asset_id);


--
-- Name: ix_asset_name; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_name ON ars.asset USING gin (internal_name public.gin_trgm_ops);


--
-- Name: ix_asset_phase; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_phase ON ars.asset USING btree (current_phase) WHERE (deleted_at IS NULL);


--
-- Name: ix_asset_status; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_status ON ars.asset USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_asset_status_history_asset; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_status_history_asset ON ars.asset_status_history USING btree (asset_id, changed_at DESC);


--
-- Name: ix_asset_trade; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_trade ON ars.asset USING gin (trade_name public.gin_trgm_ops);


--
-- Name: ix_asset_type; Type: INDEX; Schema: ars; Owner: -
--

CREATE INDEX ix_asset_type ON ars.asset USING btree (asset_type) WHERE (deleted_at IS NULL);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_action ON audit.audit_log USING btree (action);


--
-- Name: ix_audit_log_entity; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_entity ON audit.audit_log USING btree (entity_schema, entity_table, entity_id);


--
-- Name: ix_audit_log_entity_code; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_entity_code ON audit.audit_log USING btree (entity_code);


--
-- Name: ix_audit_log_timestamp; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_timestamp ON audit.audit_log USING btree ("timestamp" DESC);


--
-- Name: ix_audit_log_user_time; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_audit_log_user_time ON audit.audit_log USING btree (user_id, "timestamp" DESC);


--
-- Name: ix_change_history_log; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_change_history_log ON audit.change_history USING btree (audit_log_id);


--
-- Name: ix_e_signature_entity; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_e_signature_entity ON audit.e_signature USING btree (entity_schema, entity_table, entity_id);


--
-- Name: ix_e_signature_user; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX ix_e_signature_user ON audit.e_signature USING btree (user_id, signed_at DESC);


--
-- Name: ix_login_history_login_at; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX ix_login_history_login_at ON auth.login_history USING btree (login_at DESC);


--
-- Name: ix_refresh_token_expires; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX ix_refresh_token_expires ON auth.refresh_token USING btree (expires_at);


--
-- Name: ix_refresh_token_user_active; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX ix_refresh_token_user_active ON auth.refresh_token USING btree (user_id) WHERE (revoked_at IS NULL);


--
-- Name: ix_user_status; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX ix_user_status ON auth."user" USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_lookup_type; Type: INDEX; Schema: meta; Owner: -
--

CREATE INDEX ix_lookup_type ON meta.lookup_value USING btree (lookup_type, sort_order) WHERE (is_active = true);


--
-- Name: ix_material_batch_expiry; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_batch_expiry ON mm.material_batch USING btree (expiry_date) WHERE (deleted_at IS NULL);


--
-- Name: ix_material_batch_material; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_batch_material ON mm.material_batch USING btree (material_id);


--
-- Name: ix_material_category; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_category ON mm.material USING btree (category) WHERE (deleted_at IS NULL);


--
-- Name: ix_material_manufacturer; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_manufacturer ON mm.material USING btree (manufacturer) WHERE (deleted_at IS NULL);


--
-- Name: ix_material_name; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_name ON mm.material USING gin (material_name public.gin_trgm_ops);


--
-- Name: ix_material_status; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_status ON mm.material USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_material_substance; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_substance ON mm.material USING btree (substance_id);


--
-- Name: ix_material_type; Type: INDEX; Schema: mm; Owner: -
--

CREATE INDEX ix_material_type ON mm.material USING btree (material_type) WHERE (deleted_at IS NULL);


--
-- Name: ix_project_dates; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_dates ON prs.project USING btree (planned_start_date, planned_end_date);


--
-- Name: ix_project_milestone_project; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_milestone_project ON prs.project_milestone USING btree (project_id, planned_date);


--
-- Name: ix_project_name; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_name ON prs.project USING gin (project_name public.gin_trgm_ops);


--
-- Name: ix_project_parent; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_parent ON prs.project USING btree (parent_project_id);


--
-- Name: ix_project_phase; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_phase ON prs.project USING btree (project_phase) WHERE (deleted_at IS NULL);


--
-- Name: ix_project_pm; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_pm ON prs.project USING btree (project_manager_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_project_status; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_status ON prs.project USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_project_status_history_project; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_status_history_project ON prs.project_status_history USING btree (project_id, changed_at DESC);


--
-- Name: ix_project_team_project; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_team_project ON prs.project_team USING btree (project_id) WHERE (left_at IS NULL);


--
-- Name: ix_project_team_user; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_team_user ON prs.project_team USING btree (user_id) WHERE (left_at IS NULL);


--
-- Name: ix_project_type; Type: INDEX; Schema: prs; Owner: -
--

CREATE INDEX ix_project_type ON prs.project USING btree (project_type) WHERE (deleted_at IS NULL);


--
-- Name: uq_project_team_active; Type: INDEX; Schema: prs; Owner: -
--

CREATE UNIQUE INDEX uq_project_team_active ON prs.project_team USING btree (project_id, user_id, role) WHERE (left_at IS NULL);


--
-- Name: ix_ref_as_asset; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_as_asset ON ref.asset_substance USING btree (asset_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ref_as_substance; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_as_substance ON ref.asset_substance USING btree (substance_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ref_pa_asset; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_pa_asset ON ref.project_asset USING btree (asset_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ref_pa_project; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_pa_project ON ref.project_asset USING btree (project_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ref_ps_project; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_ps_project ON ref.project_substance USING btree (project_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ref_ps_substance; Type: INDEX; Schema: ref; Owner: -
--

CREATE INDEX ix_ref_ps_substance ON ref.project_substance USING btree (substance_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_substance_adc_antibody; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_adc_antibody ON srs.substance_adc USING btree (antibody_substance_id);


--
-- Name: ix_substance_adc_payload; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_adc_payload ON srs.substance_adc USING btree (payload_substance_id);


--
-- Name: ix_substance_alias_substance; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_alias_substance ON srs.substance_alias USING btree (substance_id);


--
-- Name: ix_substance_alias_value; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_alias_value ON srs.substance_alias USING gin (alias_value public.gin_trgm_ops);


--
-- Name: ix_substance_extra; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_extra ON srs.substance USING gin (extra);


--
-- Name: ix_substance_internal_code; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_internal_code ON srs.substance USING btree (internal_code) WHERE (deleted_at IS NULL);


--
-- Name: ix_substance_preferred_name; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_preferred_name ON srs.substance USING gin (preferred_name public.gin_trgm_ops);


--
-- Name: ix_substance_protein_hc_hash; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_protein_hc_hash ON srs.substance_protein USING btree (sequence_hash_hc);


--
-- Name: ix_substance_protein_lc_hash; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_protein_lc_hash ON srs.substance_protein USING btree (sequence_hash_lc);


--
-- Name: ix_substance_status; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_status ON srs.substance USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_substance_status_history_sub; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_status_history_sub ON srs.substance_status_history USING btree (substance_id, changed_at DESC);


--
-- Name: ix_substance_substance_type; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_substance_type ON srs.substance USING btree (substance_type) WHERE (deleted_at IS NULL);


--
-- Name: ix_substance_target; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_target ON srs.substance USING btree (target) WHERE (deleted_at IS NULL);


--
-- Name: ix_substance_xref_substance_id; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_xref_substance_id ON srs.substance_xref USING btree (substance_id);


--
-- Name: ix_substance_xref_value; Type: INDEX; Schema: srs; Owner: -
--

CREATE INDEX ix_substance_xref_value ON srs.substance_xref USING btree (xref_value);


--
-- Name: uq_substance_sm_inchi_key; Type: INDEX; Schema: srs; Owner: -
--

CREATE UNIQUE INDEX uq_substance_sm_inchi_key ON srs.substance_small_molecule USING btree (inchi_key) WHERE (inchi_key IS NOT NULL);


--
-- Name: uq_substance_xref_type_value; Type: INDEX; Schema: srs; Owner: -
--

CREATE UNIQUE INDEX uq_substance_xref_type_value ON srs.substance_xref USING btree (xref_type, xref_value) WHERE (deleted_at IS NULL);


--
-- Name: asset trg_asset_assign_code; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_assign_code BEFORE INSERT ON ars.asset FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_assign_code();


--
-- Name: asset trg_asset_audit; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_audit AFTER INSERT OR DELETE OR UPDATE ON ars.asset FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('asset_id', 'asset_code');


--
-- Name: asset trg_asset_before_update; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_before_update BEFORE UPDATE ON ars.asset FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_before_update();


--
-- Name: asset_market_id trg_asset_market_id_audit; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_market_id_audit AFTER INSERT OR DELETE OR UPDATE ON ars.asset_market_id FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('market_id_pk', '', 'ars.asset:asset_id:asset_code:asset_id');


--
-- Name: asset_market_id trg_asset_market_id_touch; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_market_id_touch BEFORE UPDATE ON ars.asset_market_id FOR EACH ROW EXECUTE FUNCTION ars.fn_touch_updated_at();


--
-- Name: asset trg_asset_status_change; Type: TRIGGER; Schema: ars; Owner: -
--

CREATE TRIGGER trg_asset_status_change AFTER UPDATE ON ars.asset FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_status_change();


--
-- Name: material trg_material_assign_code; Type: TRIGGER; Schema: mm; Owner: -
--

CREATE TRIGGER trg_material_assign_code BEFORE INSERT ON mm.material FOR EACH ROW EXECUTE FUNCTION mm.fn_material_assign_code();


--
-- Name: material trg_material_audit; Type: TRIGGER; Schema: mm; Owner: -
--

CREATE TRIGGER trg_material_audit AFTER INSERT OR DELETE OR UPDATE ON mm.material FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('material_id', 'material_code');


--
-- Name: material_batch trg_material_batch_audit; Type: TRIGGER; Schema: mm; Owner: -
--

CREATE TRIGGER trg_material_batch_audit AFTER INSERT OR DELETE OR UPDATE ON mm.material_batch FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('batch_id', '', 'mm.material:material_id:material_code:material_id');


--
-- Name: material_batch trg_material_batch_before_update; Type: TRIGGER; Schema: mm; Owner: -
--

CREATE TRIGGER trg_material_batch_before_update BEFORE UPDATE ON mm.material_batch FOR EACH ROW EXECUTE FUNCTION mm.fn_material_batch_before_update();


--
-- Name: material trg_material_before_update; Type: TRIGGER; Schema: mm; Owner: -
--

CREATE TRIGGER trg_material_before_update BEFORE UPDATE ON mm.material FOR EACH ROW EXECUTE FUNCTION mm.fn_material_before_update();


--
-- Name: project trg_project_assign_code; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_assign_code BEFORE INSERT ON prs.project FOR EACH ROW EXECUTE FUNCTION prs.fn_project_assign_code();


--
-- Name: project trg_project_audit; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_audit AFTER INSERT OR DELETE OR UPDATE ON prs.project FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', 'project_code');


--
-- Name: project trg_project_before_update; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_before_update BEFORE UPDATE ON prs.project FOR EACH ROW EXECUTE FUNCTION prs.fn_project_before_update();


--
-- Name: project_milestone trg_project_milestone_audit; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_milestone_audit AFTER INSERT OR DELETE OR UPDATE ON prs.project_milestone FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('milestone_id', '', 'prs.project:project_id:project_code:project_id');


--
-- Name: project_milestone trg_project_milestone_touch; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_milestone_touch BEFORE UPDATE ON prs.project_milestone FOR EACH ROW EXECUTE FUNCTION prs.fn_touch_updated_at();


--
-- Name: project trg_project_status_change; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_status_change AFTER UPDATE ON prs.project FOR EACH ROW EXECUTE FUNCTION prs.fn_project_status_change();


--
-- Name: project_team trg_project_team_audit; Type: TRIGGER; Schema: prs; Owner: -
--

CREATE TRIGGER trg_project_team_audit AFTER INSERT OR DELETE OR UPDATE ON prs.project_team FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('team_id', '', 'prs.project:project_id:project_code:project_id');


--
-- Name: asset_substance trg_ref_as_audit; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER trg_ref_as_audit AFTER INSERT OR DELETE OR UPDATE ON ref.asset_substance FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('asset_id', '', 'ars.asset:asset_id:asset_code:asset_id');


--
-- Name: project_asset trg_ref_pa_audit; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER trg_ref_pa_audit AFTER INSERT OR DELETE OR UPDATE ON ref.project_asset FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', '', 'prs.project:project_id:project_code:project_id');


--
-- Name: project_substance trg_ref_ps_audit; Type: TRIGGER; Schema: ref; Owner: -
--

CREATE TRIGGER trg_ref_ps_audit AFTER INSERT OR DELETE OR UPDATE ON ref.project_substance FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', '', 'prs.project:project_id:project_code:project_id');


--
-- Name: substance_adc trg_substance_adc_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_adc_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance_adc FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', '', 'srs.substance:substance_id:substance_code:substance_id');


--
-- Name: substance_alias trg_substance_alias_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_alias_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance_alias FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('alias_id', '', 'srs.substance:substance_id:substance_code:substance_id');


--
-- Name: substance trg_substance_assign_code; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_assign_code BEFORE INSERT ON srs.substance FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_assign_code();


--
-- Name: substance trg_substance_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', 'substance_code');


--
-- Name: substance trg_substance_before_update; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_before_update BEFORE UPDATE ON srs.substance FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_before_update();


--
-- Name: substance_protein trg_substance_protein_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_protein_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance_protein FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', '', 'srs.substance:substance_id:substance_code:substance_id');


--
-- Name: substance_protein trg_substance_protein_compute_hash; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_protein_compute_hash BEFORE INSERT OR UPDATE ON srs.substance_protein FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_protein_compute_hash();


--
-- Name: substance_small_molecule trg_substance_sm_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_sm_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance_small_molecule FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', '', 'srs.substance:substance_id:substance_code:substance_id');


--
-- Name: substance trg_substance_status_change; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_status_change AFTER UPDATE ON srs.substance FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_status_change();


--
-- Name: substance_xref trg_substance_xref_audit; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_xref_audit AFTER INSERT OR DELETE OR UPDATE ON srs.substance_xref FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('xref_id', '', 'srs.substance:substance_id:substance_code:substance_id');


--
-- Name: substance_xref trg_substance_xref_touch; Type: TRIGGER; Schema: srs; Owner: -
--

CREATE TRIGGER trg_substance_xref_touch BEFORE UPDATE ON srs.substance_xref FOR EACH ROW EXECUTE FUNCTION srs.fn_touch_updated_at();


--
-- Name: asset_market_id fk_asset_market_id_asset_asset_id; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT fk_asset_market_id_asset_asset_id FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id);


--
-- Name: asset_market_id fk_asset_market_id_deleted_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT fk_asset_market_id_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_market_id fk_asset_market_id_user_created_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT fk_asset_market_id_user_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_market_id fk_asset_market_id_user_updated_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_market_id
    ADD CONSTRAINT fk_asset_market_id_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_status_history fk_asset_status_history_asset_asset_id; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_status_history
    ADD CONSTRAINT fk_asset_status_history_asset_asset_id FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id);


--
-- Name: asset_status_history fk_asset_status_history_e_signature_e_signature_id; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_status_history
    ADD CONSTRAINT fk_asset_status_history_e_signature_e_signature_id FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id);


--
-- Name: asset_status_history fk_asset_status_history_user_changed_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset_status_history
    ADD CONSTRAINT fk_asset_status_history_user_changed_by FOREIGN KEY (changed_by) REFERENCES auth."user"(user_id);


--
-- Name: asset fk_asset_user_created_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset
    ADD CONSTRAINT fk_asset_user_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: asset fk_asset_user_deleted_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset
    ADD CONSTRAINT fk_asset_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: asset fk_asset_user_updated_by; Type: FK CONSTRAINT; Schema: ars; Owner: -
--

ALTER TABLE ONLY ars.asset
    ADD CONSTRAINT fk_asset_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: change_history fk_change_history_audit_log_audit_log_id; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.change_history
    ADD CONSTRAINT fk_change_history_audit_log_audit_log_id FOREIGN KEY (audit_log_id) REFERENCES audit.audit_log(log_id);


--
-- Name: e_signature fk_e_signature_audit_log_audit_log_id; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.e_signature
    ADD CONSTRAINT fk_e_signature_audit_log_audit_log_id FOREIGN KEY (audit_log_id) REFERENCES audit.audit_log(log_id);


--
-- Name: e_signature fk_e_signature_user_user_id; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.e_signature
    ADD CONSTRAINT fk_e_signature_user_user_id FOREIGN KEY (user_id) REFERENCES auth."user"(user_id);


--
-- Name: login_history fk_login_history_user_user_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.login_history
    ADD CONSTRAINT fk_login_history_user_user_id FOREIGN KEY (user_id) REFERENCES auth."user"(user_id);


--
-- Name: refresh_token fk_refresh_token_user_user_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_token
    ADD CONSTRAINT fk_refresh_token_user_user_id FOREIGN KEY (user_id) REFERENCES auth."user"(user_id);


--
-- Name: role_permission fk_role_permission_permission_permission_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permission
    ADD CONSTRAINT fk_role_permission_permission_permission_id FOREIGN KEY (permission_id) REFERENCES auth.permission(permission_id);


--
-- Name: role_permission fk_role_permission_role_role_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.role_permission
    ADD CONSTRAINT fk_role_permission_role_role_id FOREIGN KEY (role_id) REFERENCES auth.role(role_id);


--
-- Name: user_role fk_user_role_role_role_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_role
    ADD CONSTRAINT fk_user_role_role_role_id FOREIGN KEY (role_id) REFERENCES auth.role(role_id);


--
-- Name: user_role fk_user_role_user_user_id; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.user_role
    ADD CONSTRAINT fk_user_role_user_user_id FOREIGN KEY (user_id) REFERENCES auth."user"(user_id);


--
-- Name: material_batch fk_material_batch_material_material_id; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT fk_material_batch_material_material_id FOREIGN KEY (material_id) REFERENCES mm.material(material_id);


--
-- Name: material_batch fk_material_batch_user_created_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT fk_material_batch_user_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: material_batch fk_material_batch_user_deleted_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT fk_material_batch_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: material_batch fk_material_batch_user_updated_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material_batch
    ADD CONSTRAINT fk_material_batch_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: material fk_material_substance_substance_id; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT fk_material_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: material fk_material_user_created_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT fk_material_user_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: material fk_material_user_deleted_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT fk_material_user_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: material fk_material_user_updated_by; Type: FK CONSTRAINT; Schema: mm; Owner: -
--

ALTER TABLE ONLY mm.material
    ADD CONSTRAINT fk_material_user_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: project fk_project_created_by; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: project fk_project_deleted_by; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: project fk_project_manager; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_manager FOREIGN KEY (project_manager_id) REFERENCES auth."user"(user_id);


--
-- Name: project_milestone fk_project_milestone_project; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_milestone
    ADD CONSTRAINT fk_project_milestone_project FOREIGN KEY (project_id) REFERENCES prs.project(project_id) ON DELETE CASCADE;


--
-- Name: project fk_project_parent; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_parent FOREIGN KEY (parent_project_id) REFERENCES prs.project(project_id);


--
-- Name: project_relationship fk_project_relationship_project_from_project_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_relationship
    ADD CONSTRAINT fk_project_relationship_project_from_project_id FOREIGN KEY (from_project_id) REFERENCES prs.project(project_id);


--
-- Name: project_relationship fk_project_relationship_project_to_project_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_relationship
    ADD CONSTRAINT fk_project_relationship_project_to_project_id FOREIGN KEY (to_project_id) REFERENCES prs.project(project_id);


--
-- Name: project fk_project_sponsor; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_sponsor FOREIGN KEY (sponsor_id) REFERENCES auth."user"(user_id);


--
-- Name: project_status_history fk_project_status_history_e_signature_e_signature_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_status_history
    ADD CONSTRAINT fk_project_status_history_e_signature_e_signature_id FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id);


--
-- Name: project_status_history fk_project_status_history_project_project_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_status_history
    ADD CONSTRAINT fk_project_status_history_project_project_id FOREIGN KEY (project_id) REFERENCES prs.project(project_id);


--
-- Name: project_status_history fk_project_status_history_user_changed_by; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_status_history
    ADD CONSTRAINT fk_project_status_history_user_changed_by FOREIGN KEY (changed_by) REFERENCES auth."user"(user_id);


--
-- Name: project_team fk_project_team_project_project_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_team
    ADD CONSTRAINT fk_project_team_project_project_id FOREIGN KEY (project_id) REFERENCES prs.project(project_id);


--
-- Name: project_team fk_project_team_user_user_id; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project_team
    ADD CONSTRAINT fk_project_team_user_user_id FOREIGN KEY (user_id) REFERENCES auth."user"(user_id);


--
-- Name: project fk_project_updated_by; Type: FK CONSTRAINT; Schema: prs; Owner: -
--

ALTER TABLE ONLY prs.project
    ADD CONSTRAINT fk_project_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_substance fk_asset_substance_asset_asset_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT fk_asset_substance_asset_asset_id FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id);


--
-- Name: asset_substance fk_asset_substance_substance_substance_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT fk_asset_substance_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: project_asset fk_project_asset_asset_asset_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT fk_project_asset_asset_asset_id FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id);


--
-- Name: project_asset fk_project_asset_project_project_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT fk_project_asset_project_project_id FOREIGN KEY (project_id) REFERENCES prs.project(project_id);


--
-- Name: project_substance fk_project_substance_project_project_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT fk_project_substance_project_project_id FOREIGN KEY (project_id) REFERENCES prs.project(project_id);


--
-- Name: project_substance fk_project_substance_substance_substance_id; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT fk_project_substance_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: asset_substance fk_ref_as_created_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT fk_ref_as_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_substance fk_ref_as_deleted_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT fk_ref_as_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: asset_substance fk_ref_as_updated_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.asset_substance
    ADD CONSTRAINT fk_ref_as_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: project_asset fk_ref_pa_created_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT fk_ref_pa_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: project_asset fk_ref_pa_deleted_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT fk_ref_pa_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: project_asset fk_ref_pa_updated_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_asset
    ADD CONSTRAINT fk_ref_pa_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: project_substance fk_ref_ps_created_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT fk_ref_ps_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: project_substance fk_ref_ps_deleted_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT fk_ref_ps_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: project_substance fk_ref_ps_updated_by; Type: FK CONSTRAINT; Schema: ref; Owner: -
--

ALTER TABLE ONLY ref.project_substance
    ADD CONSTRAINT fk_ref_ps_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_adc fk_substance_adc_substance_antibody_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_adc
    ADD CONSTRAINT fk_substance_adc_substance_antibody_substance_id FOREIGN KEY (antibody_substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_adc fk_substance_adc_substance_linker_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_adc
    ADD CONSTRAINT fk_substance_adc_substance_linker_substance_id FOREIGN KEY (linker_substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_adc fk_substance_adc_substance_payload_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_adc
    ADD CONSTRAINT fk_substance_adc_substance_payload_substance_id FOREIGN KEY (payload_substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_adc fk_substance_adc_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_adc
    ADD CONSTRAINT fk_substance_adc_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id) ON DELETE CASCADE;


--
-- Name: substance_alias fk_substance_alias_created_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_alias
    ADD CONSTRAINT fk_substance_alias_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_alias fk_substance_alias_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_alias
    ADD CONSTRAINT fk_substance_alias_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance fk_substance_created_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT fk_substance_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: substance fk_substance_deleted_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT fk_substance_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_protein fk_substance_protein_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_protein
    ADD CONSTRAINT fk_substance_protein_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id) ON DELETE CASCADE;


--
-- Name: substance fk_substance_registered_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT fk_substance_registered_by FOREIGN KEY (registered_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_small_molecule fk_substance_small_molecule_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_small_molecule
    ADD CONSTRAINT fk_substance_small_molecule_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id) ON DELETE CASCADE;


--
-- Name: substance_status_history fk_substance_status_history_e_signature_e_signature_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_status_history
    ADD CONSTRAINT fk_substance_status_history_e_signature_e_signature_id FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id);


--
-- Name: substance_status_history fk_substance_status_history_substance_merged_to_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_status_history
    ADD CONSTRAINT fk_substance_status_history_substance_merged_to_substance_id FOREIGN KEY (merged_to_substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_status_history fk_substance_status_history_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_status_history
    ADD CONSTRAINT fk_substance_status_history_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_status_history fk_substance_status_history_user_changed_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_status_history
    ADD CONSTRAINT fk_substance_status_history_user_changed_by FOREIGN KEY (changed_by) REFERENCES auth."user"(user_id);


--
-- Name: substance fk_substance_updated_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance
    ADD CONSTRAINT fk_substance_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_xref fk_substance_xref_created_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_xref
    ADD CONSTRAINT fk_substance_xref_created_by FOREIGN KEY (created_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_xref fk_substance_xref_deleted_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_xref
    ADD CONSTRAINT fk_substance_xref_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth."user"(user_id);


--
-- Name: substance_xref fk_substance_xref_substance_substance_id; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_xref
    ADD CONSTRAINT fk_substance_xref_substance_substance_id FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id);


--
-- Name: substance_xref fk_substance_xref_updated_by; Type: FK CONSTRAINT; Schema: srs; Owner: -
--

ALTER TABLE ONLY srs.substance_xref
    ADD CONSTRAINT fk_substance_xref_updated_by FOREIGN KEY (updated_by) REFERENCES auth."user"(user_id);


--
-- PostgreSQL database dump complete
--

\unrestrict d8tfvgTGAO5mkXm0dEDsqJUh2tspmemdLeIgVSB7I7FOBitJppozmeOrQkziYzT

