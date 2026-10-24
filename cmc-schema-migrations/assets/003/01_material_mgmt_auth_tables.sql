--
-- PostgreSQL database dump
--

\restrict qD8FamVua9tVNCQSSDGcGiHVIgrKviOap4KXME4dM0n87U881CSfImEQPeCie8j

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
    CONSTRAINT app_user_role_check CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'user'::character varying])::text[])))
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
-- Name: app_user id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.app_user ALTER COLUMN id SET DEFAULT nextval('material_mgmt.app_user_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.audit_log ALTER COLUMN id SET DEFAULT nextval('material_mgmt.audit_log_id_seq'::regclass);


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
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES material_mgmt.app_user(id) ON DELETE SET NULL;


--
-- Name: auth_session auth_session_user_id_fkey; Type: FK CONSTRAINT; Schema: material_mgmt; Owner: -
--

ALTER TABLE ONLY material_mgmt.auth_session
    ADD CONSTRAINT auth_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES material_mgmt.app_user(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict qD8FamVua9tVNCQSSDGcGiHVIgrKviOap4KXME4dM0n87U881CSfImEQPeCie8j

