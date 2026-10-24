--
-- PostgreSQL database dump
--

\restrict iRdQqFwJSsoioWqocl1MyEM2SH2Jc2FILXEjdcWV3TdS6soxsimcCpVSBw9MQCa

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

--
-- Name: raw_qc_lims; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_qc_lims;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: batch; Type: TABLE; Schema: raw_qc_lims; Owner: -
--

CREATE TABLE raw_qc_lims.batch (
    batch_id text NOT NULL,
    "U_BATCHNO" text,
    "U_INHOUSEBATCHNO" text,
    "U_SUPPLIERBATCHNO" text,
    "BATCHDESC" text,
    "U_PRODUCTDESC" text,
    "U_PRODUCTCODE" text,
    "U_PRODVARIANTNAME" text,
    "PRODVARIANTID" text,
    "U_MOLECULE" text,
    "U_FACILITY" text,
    "U_PROCESSSTEP" text,
    "U_PROCESSSTEPNUMBER" text,
    "U_HARVESTNB" text,
    "U_PROJECTNO" text,
    "U_RECEIVEBATHCID" text,
    "BATCHTYPE" text,
    "BATCHSTATUS" text,
    "DISPOSITION" text,
    "U_SAMPLETYPE" text,
    "U_TESTPURPOSE" text,
    "U_TESTITEMS" text,
    "U_TESTPROCESS" text,
    "U_RISKGROUP" text,
    "U_STORAGECONDITION" text,
    "BATCHSIZE" text,
    "BATCHSIZEUNITS" text,
    "U_FINISHEDAMOUNT" text,
    "U_PACKAGEAMOUNT" text,
    "U_PACKAGSIZE" text,
    "U_PRIORITY" text,
    "U_DUEDT" timestamp without time zone,
    "CREATEDT" timestamp without time zone,
    "MODDT" timestamp without time zone,
    "RELEASEDDT" timestamp without time zone,
    "U_RELEASEDT" timestamp without time zone,
    "U_REPORTDT" timestamp without time zone,
    "U_LOGINDATE" timestamp without time zone,
    "EXPIRYDT" timestamp without time zone,
    "U_LOGINDEPARTMENT" text,
    "U_PRODUCTDEPARTMENT" text,
    "RELEASEDBY" text,
    "CREATEBY" text,
    "MODBY" text,
    "TEMPLATEFLAG" text,
    "ACTIVEFLAG" text
);


--
-- Name: result; Type: TABLE; Schema: raw_qc_lims; Owner: -
--

CREATE TABLE raw_qc_lims.result (
    result_id text NOT NULL,
    sample_id text,
    "SDCID" text,
    "KEYID2" text,
    "KEYID3" text,
    "DATASET" text,
    "PARAMLISTID" text,
    "PARAMLISTVERSIONID" text,
    "VARIANTID" text,
    "PARAMID" text,
    "PARAMTYPE" text,
    "REPLICATEID" text,
    "MANDATORYFLAG" text,
    "ENTEREDVALUE" text,
    "ENTEREDTEXT" text,
    "ENTEREDUNITS" text,
    "ENTEREDOPERATOR" text,
    "ENTEREDQUALIFIER" text,
    "TRANSFORMVALUE" text,
    "TRANSFORMTEXT" text,
    "TRANSFORMRULE" text,
    "OPERATORRULE" text,
    "CALCRULE" text,
    "DISPLAYVALUE" text,
    "DISPLAYUNITS" text,
    "RELEASEDFLAG" text,
    "REPORTFLAG" text,
    "VALUESTATUS" text,
    "CONDITION" text,
    "S_QCEVALSTATUS" text,
    "S_ACOVERRIDDENFLAG" text,
    "INSTRUMENTID" text,
    "INSTRUMENTFIELDID" text,
    "S_ANALYSTID" text,
    "CREATEBY" text,
    "CREATEDT" timestamp without time zone,
    "MODBY" text,
    "MODDT" timestamp without time zone,
    "ACTIVEFLAG" text
);


--
-- Name: sample; Type: TABLE; Schema: raw_qc_lims; Owner: -
--

CREATE TABLE raw_qc_lims.sample (
    sample_id text NOT NULL,
    batch_id text,
    "SAMPLEDESC" text,
    "U_PRODUCTDESC" text,
    "U_BATCHNO" text,
    "SAMPLETYPEID" text,
    "SAMPLESUBTYPEID" text,
    "U_SAMPLETYPE" text,
    "QCSAMPLETYPE" text,
    "SPECIMENTYPE" text,
    "CLASSIFICATION" text,
    "SAMPLESTATUS" text,
    "U_BATCHSTATUS" text,
    "U_TESTRESULT" text,
    "U_FINALRESULTFLAG" text,
    "U_RETESTEDFLAG" text,
    "U_REMEASUREDFLAG" text,
    "U_REMEASUREDREPLICATE" text,
    "U_RESAMPLEFLAG" text,
    "U_PARENTSAMPLEID" text,
    "BASEDONSAMPLEID" text,
    "U_RESAMPLEID" text,
    "U_SAMPBATCHID" text,
    "U_MONITORSAMPLEID" text,
    "MATERIALID" text,
    "PRODUCTID" text,
    "PROJECTID" text,
    "BATCHSTAGEID" text,
    "INSTRUMENTID" text,
    "PRIORITY" text,
    "CREATEDT" timestamp without time zone,
    "RECEIVEDDT" timestamp without time zone,
    "STARTTESTINGDT" timestamp without time zone,
    "COMPLETEDT" timestamp without time zone,
    "DUEDT" timestamp without time zone,
    "MODDT" timestamp without time zone,
    "U_RECEIVEDDATE" timestamp without time zone,
    "SUBMITTERID" text,
    "RECEIVEDBY" text,
    "U_RECEIVEDBY" text,
    "ASSIGNEDANALYSTID" text,
    "TESTINGDEPARTMENTID" text,
    "ASSIGNEDDEPARTMENTID" text,
    "TEMPLATEFLAG" text,
    "ACTIVEFLAG" text,
    "U_LESSAMPLEFLAG" text
);


--
-- Name: batch batch_pkey; Type: CONSTRAINT; Schema: raw_qc_lims; Owner: -
--

ALTER TABLE ONLY raw_qc_lims.batch
    ADD CONSTRAINT batch_pkey PRIMARY KEY (batch_id);


--
-- Name: result result_pkey; Type: CONSTRAINT; Schema: raw_qc_lims; Owner: -
--

ALTER TABLE ONLY raw_qc_lims.result
    ADD CONSTRAINT result_pkey PRIMARY KEY (result_id);


--
-- Name: sample sample_pkey; Type: CONSTRAINT; Schema: raw_qc_lims; Owner: -
--

ALTER TABLE ONLY raw_qc_lims.sample
    ADD CONSTRAINT sample_pkey PRIMARY KEY (sample_id);


--
-- Name: idx_raw_batch_batchno; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_batch_batchno ON raw_qc_lims.batch USING btree ("U_BATCHNO");


--
-- Name: idx_raw_batch_moddt; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_batch_moddt ON raw_qc_lims.batch USING btree ("MODDT");


--
-- Name: idx_raw_result_moddt; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_result_moddt ON raw_qc_lims.result USING btree ("MODDT");


--
-- Name: idx_raw_result_paramlist; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_result_paramlist ON raw_qc_lims.result USING btree ("PARAMLISTID");


--
-- Name: idx_raw_result_sample; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_result_sample ON raw_qc_lims.result USING btree (sample_id);


--
-- Name: idx_raw_sample_batch; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_sample_batch ON raw_qc_lims.sample USING btree (batch_id);


--
-- Name: idx_raw_sample_batchno; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_sample_batchno ON raw_qc_lims.sample USING btree ("U_BATCHNO");


--
-- Name: idx_raw_sample_moddt; Type: INDEX; Schema: raw_qc_lims; Owner: -
--

CREATE INDEX idx_raw_sample_moddt ON raw_qc_lims.sample USING btree ("MODDT");


--
-- PostgreSQL database dump complete
--

\unrestrict iRdQqFwJSsoioWqocl1MyEM2SH2Jc2FILXEjdcWV3TdS6soxsimcCpVSBw9MQCa

