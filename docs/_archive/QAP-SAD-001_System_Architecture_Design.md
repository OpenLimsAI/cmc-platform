# QAP-SAD-001 Quality Analysis Platform System Architecture Design

**Quality Analysis Platform**

System Architecture Design Document

QAP-SAD-001 | Version 1.0 | 2026-05-13

|                 |               |                    |            |
|-----------------|---------------|--------------------|------------|
| **Field**       | **Value**     | **Field**          | **Value**  |
| **Document ID** | QAP-SAD-001   | **Version**        | 1.0        |
| **Status**      | Draft         | **Date**           | 2026-05-13 |
| **Author**      | CMC Data Team | **Classification** | Internal   |

# 1. Overview

## 1.1 Purpose

This document defines the system architecture for the Quality AnalysisPlatform (QAP), a web-based analytical application for CMC quality data.QAP provides interactive statistical analysis, visualization, andreporting capabilities across R&D and QC laboratory data sourced fromtwo independent LIMS systems.

## 1.2 Scope

- R&D LIMS data analysis (SampleManager / Oracle, ETL to PostgreSQL)

- QC LIMS data analysis (LabVantage / Oracle, ETL to PostgreSQL)

- Cross-domain analytics including Continued Process Verification (CPV)

- Bioprocess parameter integration for CPV and future AI/ML data mining

- Statistical computation: trend analysis, similarity, stability,
  Cpk/Ppk

- Export and reporting (PDF, Excel)

## 1.3 Out of Scope

- ETL pipelines (managed by separate, independent ETL programs)

- LIMS system administration or data entry

- ERP/MES integration (future phase)

## 1.4 Design Principles

- Read-only consumer: QAP never writes to LIMS source systems or
  raw/staging schemas

- Schema isolation: each data source occupies its own raw/staging/app
  schema

- Unified entity layer: cross-domain queries go through app_unified, not
  ad-hoc joins

- API-first: all frontend data access goes through versioned REST
  endpoints

- Stateless backend: no server-side session state; JWT for
  authentication

- Progressive enhancement: start with core modules, extend without
  refactoring

# 2. System Context

## 2.1 External Systems

QAP interacts with the following external systems, all through theshared PostgreSQL database:

- SampleManager (R&D LIMS): Oracle DB → R&D ETL script → raw_rd_lims →
  staging_rd → app_rd

- LabVantage (QC LIMS): Oracle DB → QC ETL script → raw_qc_lims →
  staging_qc → app_qc

- Lucullus (Bioprocess): Lucullus DB → Bioprocess ETL → raw_bioprocess →
  staging_bioprocess

- cmc_data_platform (PostgreSQL 16): the shared analytical database on
  the Linux VM

## 2.2 Data Flow Architecture

The system follows a four-layer data architecture within a singlePostgreSQL database (cmc_data_platform):

- Raw Layer (raw_*): verbatim copy of source system extracts,
  append-only, no transformation

- Staging Layer (staging_*): cleaned, normalized, typed data with
  foreign key relationships

- Dimension Layer (meta): shared reference data (projects, methods,
  employees, ETL watermarks)

- Application Layer (app_*): analytics-ready views and materialized
  views consumed by the API

A key addition in this architecture is the app_unified schema, whichprovides cross-domain views that join R&D quality results, QC releasedata, and bioprocess parameters on batch_number. This unified layer isthe single entry point for CPV dashboards and future AI/ML pipelines,eliminating data silos.

# 3. Component Architecture

## 3.1 Technology Stack

|                |                              |                                                                             |
|----------------|------------------------------|-----------------------------------------------------------------------------|
| **Component**  | **Technology**               | **Responsibility**                                                          |
| Frontend       | React 18 + TypeScript + Vite | Interactive dashboards, chart rendering (Recharts/Plotly), user interaction |
| Backend API    | FastAPI (Python 3.11+)       | RESTful endpoints, query orchestration, statistical computation, auth       |
| Database       | PostgreSQL 16                | Persistent storage, materialized views for app layer, full-text search      |
| Cache          | Redis (optional phase 2)     | Query result caching, session management                                    |
| ETL (external) | Python standalone scripts    | LIMS data extraction and loading (out of scope for this system)             |

## 3.2 Frontend Architecture

The React frontend is organized by feature domain. Each analysis moduleis a self-contained page with its own filter panel, chart area, and datatable. Shared components include:

- FilterPanel: project, batch, method, date range, data source (R&D / QC
  / All) selector

- ChartContainer: unified wrapper for Recharts/Plotly with
  export-to-image

- DataTable: sortable, filterable result table with pagination

- AnalysisToolbar: common controls for statistical parameters
  (confidence level, control limits, etc.)

## 3.3 Backend Architecture

The FastAPI backend follows a layered pattern:

- API Layer (app/api/v1/): route definitions, request validation,
  response serialization

- Service Layer (app/services/): business logic and statistical engines
  (trend_engine, similarity_engine, cpv_engine, stability_engine)

- Data Access Layer (app/models/): SQLAlchemy ORM models mapped to
  app_* and meta schemas

- Schema Layer (app/schemas/): Pydantic request/response models for type
  safety

The service layer is where all statistical computations live. Eachengine module encapsulates a family of related analyses (e.g., thetrend_engine handles control charts, Nelson rules, OOT detection, andregression). This makes it straightforward to port proven functions fromthe legacy Streamlit project.

# 4. Data Architecture

## 4.1 Database Schema Map

|                    |            |             |                                                              |
|--------------------|------------|-------------|--------------------------------------------------------------|
| **Schema**         | **Source** | **Layer**   | **Description**                                              |
| raw_rd_lims        | R&D LIMS   | Raw         | SampleManager raw extract (sample, test, result)             |
| raw_qc_lims        | QC LIMS    | Raw         | LabVantage raw extract (TBD, pending ETL)                    |
| raw_bioprocess     | Lucullus   | Raw         | Bioreactor process data, timeseries signals                  |
| staging_rd         | R&D LIMS   | Staging     | Cleaned & normalized: sample_clean, test_clean, result_clean |
| staging_qc         | QC LIMS    | Staging     | Cleaned & normalized QC data (TBD)                           |
| staging_bioprocess | Lucullus   | Staging     | Standardized & resampled timeseries                          |
| meta               | Manual/MDM | Dimension   | dim_project, dim_method, dim_employee, etl_watermark         |
| app_rd             | Derived    | Application | R&D analytics views (sample overview, turnaround, workload)  |
| app_qc             | Derived    | Application | QC analytics views (release testing, stability, trending)    |
| app_unified        | Derived    | Application | Cross-domain unified views for CPV, AI/ML                    |

## 4.2 The Unified Layer (app_unified)

The app_unified schema solves the cross-domain data silo problem. Itprovides views that merge quality results from both LIMS systems withbioprocess parameters, keyed on batch_number. This is essential for:

- CPV Dashboards: correlating process parameters (temperature, pH, DO,
  agitation) with quality attributes (purity, potency, aggregation) on a  per-batch basis

- AI/ML Data Mining: feeding a single, consistent dataset to analytical
  models without manual data wrangling

- Cross-system comparability: comparing QC release results with R&D
  characterization data for the same batch

### 4.2.1 Core Unified Views

v_unified_batch: master batch dimension joining batch_number across bothLIMS schemas and bioprocess data, with product, project, andmanufacturing date attributes.

v_unified_quality_result: all quality/analytical results from R&D andQC, normalized to a common structure (batch_number, attribute,value_num, value_str, unit, method_code, source_system, test_date).

v_unified_batch_profile: pivoted view combining process parameters (fromstaging_bioprocess) and quality attributes (fromv_unified_quality_result) for each batch, designed for CPV charting andmultivariate analysis.

## 4.3 Existing Data Model (Staging Layer)

The R&D LIMS staging layer already has a clean three-table relationalmodel:

- staging_rd.sample_clean: sample_id (PK), project_id, batch_number,
  sample_name, status, timepoint, timepoint_unit, timestamps

- staging_rd.test_clean: test_id (PK), sample_id (FK), method_code,
  method_name, status, timestamps, tester, group_id

- staging_rd.result_clean: result_id (PK), test_id (FK), attribute,
  value_num, value_str, unit, result_type, judgement, timestamps

The QC LIMS staging layer (staging_qc) will follow an analogousstructure once the QC ETL is implemented. Field naming conventions willmirror staging_rd for consistency.

## 4.4 Dimension Tables (meta)

Shared reference data used across all schemas:

- meta.dim_project: project_id (PK), project_name, project_type

- meta.dim_method: method_code (PK), method_name, std_minutes,
  target_days

- meta.dim_employee: employee_id (PK), employee_name, department

- meta.etl_watermark: job_name (PK), source_system, target_table,
  last_success_ts, status tracking

# 5. Analysis Module Specification

|                     |                 |                                                                                                   |
|---------------------|-----------------|---------------------------------------------------------------------------------------------------|
| **Module**          | **Data Source** | **Key Features**                                                                                  |
| Similarity Analysis | R&D / QC        | Biosimilar comparability, profile overlay, statistical equivalence (f2, T-test, equivalence test) |
| Trend Analysis      | QC / R&D        | Control chart (X-bar, R, I-MR), Nelson rules, OOT/OOS flagging, regression                        |
| Stability Analysis  | QC / R&D        | ICH Q1E shelf-life estimation, Arrhenius modeling, poolability test                               |
| CPV Dashboard       | Unified         | Process parameter + quality attribute correlation, Cpk/Ppk, control charts, stage-wise trending   |
| Release Testing     | QC              | Batch release summary, specification compliance, CoA data extraction                              |
| Lab Operations      | R&D / QC        | Turnaround time, workload, backlog monitoring (from existing app_rd views)                        |

## 5.1 CPV Architecture Detail

Continued Process Verification is the most architecturally complexmodule because it requires data from multiple sources:

- Process Parameters: from staging_bioprocess (Lucullus timeseries,
  resampled to per-batch summary statistics: mean, min, max, SD for each  parameter)

- Quality Attributes: from app_rd/app_qc (analytical results per batch:
  purity by SEC, charge variants by CEX, potency, etc.)

- The app_unified.v_unified_batch_profile view joins these two domains
  on batch_number, producing a single row per batch with both process  and quality columns.

The CPV engine computes Cpk/Ppk, generates I-MR and X-bar/R charts,applies Nelson rules, and supports stage-based trending (Stage 1qualification vs Stage 2 monitoring). All chart data is returned asstructured JSON; the frontend renders it with Recharts/Plotly.

## 5.2 Data Source Selection

Every analysis module supports a data_source parameter with threeoptions:

- RD: query only app_rd / staging_rd schemas

- QC: query only app_qc / staging_qc schemas

- ALL: query through app_unified views (automatic cross-system join)

This selection is exposed in the frontend as a global filter toggle andpassed to the API in every request.

# 6. API Design Overview

## 6.1 Route Structure

|                             |            |          |                                                        |
|-----------------------------|------------|----------|--------------------------------------------------------|
| **Endpoint Pattern**        | **Method** | **Auth** | **Description**                                        |
| /api/v1/samples             | GET        | Required | Paginated sample listing with filter/sort              |
| /api/v1/results             | GET        | Required | Result data with attribute/batch/project filters       |
| /api/v1/analysis/trend      | POST       | Required | Trend analysis computation (control chart, regression) |
| /api/v1/analysis/similarity | POST       | Required | Similarity/comparability analysis                      |
| /api/v1/analysis/cpv        | POST       | Required | CPV dashboard data (process + quality)                 |
| /api/v1/analysis/stability  | POST       | Required | Stability data analysis and modeling                   |
| /api/v1/meta/projects       | GET        | Required | Project dimension lookup                               |
| /api/v1/meta/methods        | GET        | Required | Method dimension lookup                                |
| /api/v1/export/{format}     | POST       | Required | Export analysis results (PDF, Excel, CSV)              |

## 6.2 Conventions

- Base path: /api/v1/ with version prefix for future migration

- Pagination: offset/limit with total count in response header

- Filtering: query parameters for GET; structured JSON body for POST
  (analysis endpoints)

- Response format: { data: [...], meta: { total, page, ... }, errors:
  [] }

- Error codes: standard HTTP codes; 422 for validation; domain-specific
  error codes in body

- Authentication: JWT Bearer token (implementation in Phase 2; Phase 1
  can use API key)

# 7. Project Structure

|                          |                                                              |
|--------------------------|--------------------------------------------------------------|
| **Path**                 | **Description**                                              |
| backend/app/main.py      | FastAPI application entry point                              |
| backend/app/api/v1/      | API route modules (samples, results, analysis, meta, export) |
| backend/app/core/        | Config, security, database connection                        |
| backend/app/models/      | SQLAlchemy / Pydantic models                                 |
| backend/app/services/    | Business logic: trend, similarity, cpv, stability engines    |
| backend/app/schemas/     | Request/response Pydantic schemas                            |
| backend/tests/           | pytest test suite                                            |
| frontend/src/pages/      | Route-level page components                                  |
| frontend/src/components/ | Shared UI components (charts, filters, tables)               |
| frontend/src/services/   | API client layer (axios/fetch wrappers)                      |
| frontend/src/hooks/      | Custom React hooks (useQuery, useAnalysis, etc.)             |
| frontend/src/types/      | TypeScript type definitions                                  |
| docs/                    | Architecture, data model, API spec, UI design documents      |

# 8. Deployment Architecture

## 8.1 Target Environment

Single Linux VM deployment with all services co-located. PostgreSQL 16runs natively (not in Docker) on the VM.

|                 |                      |                                                         |
|-----------------|----------------------|---------------------------------------------------------|
| **Service**     | **Runtime**          | **Notes**                                               |
| FastAPI Backend | Uvicorn, port 8000   | Systemd service or Docker container on Linux VM         |
| React Frontend  | Nginx, port 80/443   | Static build served by Nginx reverse proxy              |
| PostgreSQL 16   | Native on Linux VM   | cmc_data_platform database, listen on 5432              |
| R&D LIMS ETL    | Cron / systemd timer | Independent Python script, daily incremental sync       |
| QC LIMS ETL     | Cron / systemd timer | Independent Python script, daily incremental sync (TBD) |

## 8.2 Development Workflow

- Development on office PC (PyCharm + Miniconda for backend, VS Code for
  frontend)

- Git push to central repository

- Linux VM: git pull, run tests, restart services

- Database migrations managed via Alembic (backend/alembic/)

# 9. Security Considerations

- Database access: QAP connects to PostgreSQL with a read-only
  application user (qap_reader) that has SELECT-only grants on app_*  and meta schemas. No write access to raw/staging schemas.

- API authentication: JWT-based authentication with role-based access
  control (admin, analyst, viewer)

- CORS: restricted to known frontend origins

- Input validation: all API inputs validated via Pydantic schemas;
  parameterized SQL queries only

- Network: PostgreSQL listens on localhost or internal network only;
  Nginx handles TLS termination

# 10. Future Considerations

## 10.1 AI/ML Data Mining Integration

The app_unified schema is designed with future AI/ML consumption inmind. The v_unified_batch_profile view provides a flat, feature-richdataset suitable for:

- Multivariate data analysis (PCA, PLS) for process understanding

- Predictive modeling: correlating process parameter trajectories with
  final quality outcomes

- Anomaly detection on incoming batch data

When ready, a dedicated app_ml schema can be added to host featureengineering views and model metadata, with no changes needed to theexisting data pipeline.

## 10.2 Phase Roadmap

- Phase 1 (MVP): FastAPI + React scaffold, R&D LIMS trend analysis and
  similarity modules, basic auth

- Phase 2: QC LIMS ETL integration, release testing module, stability
  analysis, JWT auth

- Phase 3: CPV dashboard with bioprocess data integration, app_unified
  views, Cpk/Ppk

- Phase 4: AI/ML analytics, advanced reporting, Redis caching,
  multi-user RBAC

Appendix A: Document Deliverables Checklist

The following documents will be produced as part of the QAP project:

- QAP-SAD-001: System Architecture Design (this document)

- QAP-DDM-001: Detailed Data Model Design (ER diagrams, DDL, app_unified
  specification)

- QAP-API-001: API Design Specification (OpenAPI/Swagger,
  request/response schemas)

- QAP-UIA-001: UI Information Architecture (page hierarchy, wireframes,
  component catalog)

- QAP-AMS-001: Analysis Module Specification (algorithm definitions, I/O
  contracts)

- QAP-PCS-001: Project Structure and Coding Standards
