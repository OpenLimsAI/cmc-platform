# QAP-SAD-001 质量分析平台 系统架构设计

**Quality Analysis Platform**

**质量分析平台**

系统架构设计文档

QAP-SAD-001 | V1.0 | 2026-05-13

|              |             |          |            |
|--------------|-------------|----------|------------|
| **字段**     | **值**      | **字段** | **值**     |
| **文档编号** | QAP-SAD-001 | **版本** | 1.0        |
| **状态**     | 草稿        | **日期** | 2026-05-13 |
| **编制**     | CMC数据团队 | **密级** | 内部       |

# 1. 概述

## 1.1 文档目的

本文档定义质量分析平台（Quality Analysis Platform,QAP）的系统架构。QAP是一个基于Web的CMC质量数据分析应用，提供交互式统计分析、可视化和报告功能，覆盖研发实验室和QC实验室两套独立的LIMS系统数据。

## 1.2 范围

- 研发LIMS数据分析（SampleManager / Oracle，ETL至PostgreSQL）

- QC LIMS数据分析（LabVantage / Oracle，ETL至PostgreSQL）

- 跨域分析，包括持续工艺验证（CPV）

- 生物工艺参数集成，用于CPV及未来AI/ML数据挖掘

- 统计计算：趋势分析、相似性分析、稳定性分析、Cpk/Ppk

- 导出与报告（PDF、Excel）

## 1.3 范围外

- ETL管道（由独立的ETL程序管理）

- LIMS系统管理或数据录入

- ERP/MES集成（未来阶段）

## 1.4 设计原则

- 只读消费者：QAP不向LIMS源系统或raw/staging schema写入任何数据

- Schema隔离：每个数据源占据独立的raw/staging/app schema

- 统一实体层：跨域查询统一走app_unified，不做ad-hoc跨schema join

- API优先：所有前端数据访问通过带版本号的REST接口

- 无状态后端：不保存服务器端会话状态，使用JWT认证

- 渐进式扩展：从核心模块起步，后续扩展无需重构

# 2. 系统上下文

## 2.1 外部系统

QAP通过共享的PostgreSQL数据库与以下外部系统交互：

- SampleManager（研发LIMS）：Oracle DB → 研发ETL脚本 → raw_rd_lims →
  staging_rd → app_rd

- LabVantage（QC LIMS）：Oracle DB → QC ETL脚本 → raw_qc_lims →
  staging_qc → app_qc

- Lucullus（生物工艺）：Lucullus DB → Bioprocess ETL → raw_bioprocess →
  staging_bioprocess

- cmc_data_platform（PostgreSQL 16）：Linux虚拟机上的共享分析数据库

## 2.2 数据流架构

系统在单一PostgreSQL数据库（cmc_data_platform）内采用四层数据架构：

- 原始层（raw_*）：源系统抽取的原始副本，仅追加，不做任何转换

- 清洗层（staging_*）：清洗、归一化、类型化的数据，建立外键关系

- 维度层（meta）：共享参考数据（项目、方法、人员、ETL水位线）

- 应用层（app_*）：面向分析的视图和物化视图，供API层消费

本架构的关键新增是app_unifiedschema，它提供跨域视图，以batch_number为关联键合并研发质量数据、QC放行数据和生物工艺参数。这个统一层是CPV看板和未来AI/ML管道的唯一入口，从根本上消除数据孤岛。

# 3. 组件架构

## 3.1 技术选型

|             |                              |                                                   |
|-------------|------------------------------|---------------------------------------------------|
| **组件**    | **技术选型**                 | **职责**                                          |
| 前端        | React 18 + TypeScript + Vite | 交互式看板、图表渲染（Recharts/Plotly）、用户交互 |
| 后端API     | FastAPI (Python 3.11+)       | RESTful接口、查询编排、统计计算、认证鉴权         |
| 数据库      | PostgreSQL 16                | 持久化存储、物化视图、全文检索                    |
| 缓存        | Redis（Phase 2可选）         | 查询结果缓存、会话管理                            |
| ETL（外部） | Python独立脚本               | LIMS数据抽取与加载（不在本系统范围内）            |

## 3.2 前端架构

前端按功能域组织，每个分析模块为独立页面，包含过滤面板、图表区域和数据表格。共享组件包括：

- FilterPanel：项目、批次、方法、日期范围、数据源（研发/QC/全部）选择器

- ChartContainer：Recharts/Plotly统一包装器，支持导出为图片

- DataTable：可排序、可过滤的结果表格，支持分页

- AnalysisToolbar：统计参数通用控件（置信水平、控制限等）

## 3.3 后端架构

FastAPI后端采用分层模式：

- API层（app/api/v1/）：路由定义、请求校验、响应序列化

- 服务层（app/services/）：业务逻辑和统计引擎（trend_engine,
  similarity_engine, cpv_engine, stability_engine）

- 数据访问层（app/models/）：SQLAlchemy ORM模型，映射至app_*和meta
  schema

- Schema层（app/schemas/）：Pydantic请求/响应模型，保证类型安全

服务层是所有统计计算的所在。每个引擎模块封装一类相关分析（例如trend_engine负责控制图、Nelson规则、OOT检测和回归分析）。这种设计便于从老项目（Streamlit版本）迁移已验证的分析函数。

# 4. 数据架构

## 4.1 Schema全景

|                    |            |          |                                                      |
|--------------------|------------|----------|------------------------------------------------------|
| **Schema**         | **数据源** | **层级** | **说明**                                             |
| raw_rd_lims        | 研发LIMS   | 原始层   | SampleManager原始抽取（sample, test, result）        |
| raw_qc_lims        | QC LIMS    | 原始层   | LabVantage原始抽取（待ETL打通）                      |
| raw_bioprocess     | Lucullus   | 原始层   | 生物反应器工艺数据、时序信号                         |
| staging_rd         | 研发LIMS   | 清洗层   | 清洗归一化：sample_clean, test_clean, result_clean   |
| staging_qc         | QC LIMS    | 清洗层   | 清洗归一化QC数据（待建）                             |
| staging_bioprocess | Lucullus   | 清洗层   | 标准化与重采样时序数据                               |
| meta               | 手工/MDM   | 维度层   | dim_project, dim_method, dim_employee, etl_watermark |
| app_rd             | 衍生       | 应用层   | 研发分析视图（样品总览、周转时间、工作量）           |
| app_qc             | 衍生       | 应用层   | QC分析视图（放行检验、稳定性、趋势）                 |
| app_unified        | 衍生       | 应用层   | 跨域统一视图，用于CPV、AI/ML数据挖掘                 |

## 4.2 统一层（app_unified）

app_unifiedschema解决跨域数据孤岛问题。它提供视图，以batch_number为键合并两套LIMS的质量结果与生物工艺参数。核心用途：

- CPV看板：将工艺参数（温度、pH、DO、搅拌速度）与质量属性（纯度、效价、聚集体）按批次关联

- AI/ML数据挖掘：提供单一、一致的数据集，无需手动拼接

- 跨系统可比性：对比同一批次的QC放行结果与研发表征数据

### 4.2.1 核心统一视图

v_unified_batch：主批次维度，跨两套LIMS和工艺数据的batch_number合并，包含产品、项目、生产日期等属性。

v_unified_quality_result：所有质量/分析结果的统一视图，归一化为统一结构（batch_number,attribute, value_num, value_str, unit, method_code, source_system,test_date）。

v_unified_batch_profile：透视视图，合并工艺参数（来自staging_bioprocess）和质量属性（来自v_unified_quality_result），每批次一行，用于CPV作图和多变量分析。

## 4.3 现有数据模型（清洗层）

研发LIMS清洗层已有清晰的三表关系模型：

- staging_rd.sample_clean：sample_id (PK), project_id, batch_number,
  sample_name, status, timepoint, timepoint_unit, 时间戳

- staging_rd.test_clean：test_id (PK), sample_id (FK), method_code,
  method_name, status, 时间戳, tester, group_id

- staging_rd.result_clean：result_id (PK), test_id (FK), attribute,
  value_num, value_str, unit, result_type, judgement, 时间戳

QC LIMS清洗层（staging_qc）将在QCETL实施后采用镜像结构，字段命名约定与staging_rd保持一致。

## 4.4 维度表（meta）

跨所有schema共享的参考数据：

- meta.dim_project：project_id (PK), project_name, project_type

- meta.dim_method：method_code (PK), method_name, std_minutes,
  target_days

- meta.dim_employee：employee_id (PK), employee_name, department

- meta.etl_watermark：job_name (PK), source_system, target_table,
  last_success_ts, 状态跟踪

# 5. 分析模块规格

|            |            |                                                                         |
|------------|------------|-------------------------------------------------------------------------|
| **模块**   | **数据源** | **核心功能**                                                            |
| 相似性分析 | 研发/QC    | 生物类似药可比性分析、谱图叠加、统计学等效检验（f2、T检验、等效性检验） |
| 趋势分析   | QC/研发    | 控制图（X-bar, R, I-MR）、Nelson规则、OOT/OOS标记、回归分析             |
| 稳定性分析 | QC/研发    | ICH Q1E货架期估算、Arrhenius模型、可合并性检验                          |
| CPV看板    | 统一层     | 工艺参数+质量属性关联、Cpk/Ppk、控制图、分阶段趋势                      |
| 放行检验   | QC         | 批放行汇总、标准符合性、CoA数据提取                                     |
| 实验室运营 | 研发/QC    | 周转时间、工作量、积压监控（复用现有app_rd视图）                        |

## 5.1 CPV架构详解

持续工艺验证是架构上最复杂的模块，因为它需要多源数据：

- 工艺参数：来自staging_bioprocess（Lucullus时序数据，重采样为每批次汇总统计：均值、最小值、最大值、标准差）

- 质量属性：来自app_rd/app_qc（每批次的分析结果：SEC纯度、CEX电荷异构体、效价等）

- app_unified.v_unified_batch_profile视图以batch_number关联两个域，生成每批次一行的工艺+质量合并数据

CPV引擎计算Cpk/Ppk、生成I-MR和X-bar/R控制图、应用Nelson规则，支持分阶段趋势（Stage1验证 vs Stage2监控）。所有图表数据以结构化JSON返回，前端用Recharts/Plotly渲染。

## 5.2 数据源选择

每个分析模块支持data_source参数，三个选项：

- RD：仅查询app_rd / staging_rd schema

- QC：仅查询app_qc / staging_qc schema

- ALL：通过app_unified视图查询（自动跨系统合并）

此选择在前端作为全局过滤器暴露，并在每个API请求中传递。

# 6. API设计概览

## 6.1 路由结构

|                             |          |          |                                      |
|-----------------------------|----------|----------|--------------------------------------|
| **接口路径**                | **方法** | **认证** | **说明**                             |
| /api/v1/samples             | GET      | 需要     | 分页样品列表，支持过滤与排序         |
| /api/v1/results             | GET      | 需要     | 检测结果数据，支持属性/批次/项目过滤 |
| /api/v1/analysis/trend      | POST     | 需要     | 趋势分析计算（控制图、回归）         |
| /api/v1/analysis/similarity | POST     | 需要     | 相似性/可比性分析                    |
| /api/v1/analysis/cpv        | POST     | 需要     | CPV看板数据（工艺+质量）             |
| /api/v1/analysis/stability  | POST     | 需要     | 稳定性数据分析与建模                 |
| /api/v1/meta/projects       | GET      | 需要     | 项目维度查询                         |
| /api/v1/meta/methods        | GET      | 需要     | 方法维度查询                         |
| /api/v1/export/{format}     | POST     | 需要     | 导出分析结果（PDF、Excel、CSV）      |

## 6.2 约定

- 基础路径：/api/v1/，带版本前缀以便未来迁移

- 分页：offset/limit，响应头中返回总数

- 过滤：GET使用查询参数；POST（分析接口）使用结构化JSON body

- 响应格式：{ data: [...], meta: { total, page, ... }, errors: [] }

- 错误码：标准HTTP状态码；422用于校验失败；业务错误码在响应体中返回

- 认证：JWT Bearer Token（Phase 2实现；Phase 1可用API Key）

# 7. 项目目录结构

|                          |                                                         |
|--------------------------|---------------------------------------------------------|
| **路径**                 | **说明**                                                |
| backend/app/main.py      | FastAPI应用入口                                         |
| backend/app/api/v1/      | API路由模块（samples, results, analysis, meta, export） |
| backend/app/core/        | 配置、安全、数据库连接                                  |
| backend/app/models/      | SQLAlchemy / Pydantic 模型                              |
| backend/app/services/    | 业务逻辑：趋势引擎、相似性引擎、CPV引擎、稳定性引擎     |
| backend/app/schemas/     | 请求/响应Pydantic schema                                |
| backend/tests/           | pytest测试套件                                          |
| frontend/src/pages/      | 路由级页面组件                                          |
| frontend/src/components/ | 共享UI组件（图表、过滤器、数据表格）                    |
| frontend/src/services/   | API客户端层（axios/fetch封装）                          |
| frontend/src/hooks/      | 自定义React Hooks（useQuery, useAnalysis等）            |
| frontend/src/types/      | TypeScript类型定义                                      |
| docs/                    | 架构、数据模型、API规格、UI设计文档                     |

# 8. 部署架构

## 8.1 目标环境

单台Linux虚拟机部署，所有服务共置。PostgreSQL16在VM上原生运行（非Docker）。

|               |                      |                                       |
|---------------|----------------------|---------------------------------------|
| **服务**      | **运行环境**         | **备注**                              |
| FastAPI后端   | Uvicorn, 端口8000    | Linux VM上的systemd服务或Docker容器   |
| React前端     | Nginx, 端口80/443    | 静态构建产物由Nginx反向代理分发       |
| PostgreSQL 16 | Linux VM原生运行     | cmc_data_platform数据库，监听5432端口 |
| 研发LIMS ETL  | Cron / systemd timer | 独立Python脚本，每日增量同步          |
| QC LIMS ETL   | Cron / systemd timer | 独立Python脚本，每日增量同步（待建）  |

## 8.2 开发工作流

- 在办公 PC上开发（PyCharm + Miniconda用于后端，VS Code用于前端）

- Git push至中央仓库

- Linux VM：git pull、运行测试、重启服务

- 数据库迁移通过Alembic管理（backend/alembic/）

# 9. 安全考量

- 数据库访问：QAP使用只读应用用户（qap_reader）连接PostgreSQL，仅对app_*和meta
  schema有SELECT权限，不可写入raw/staging schema

- API认证：基于JWT的认证，支持角色控制（admin, analyst, viewer）

- CORS：仅允许已知前端源

- 输入校验：所有API输入通过Pydantic schema校验；仅使用参数化SQL查询

- 网络：PostgreSQL仅监听localhost或内网；Nginx负责TLS终止

# 10. 未来规划

## 10.1 AI/ML数据挖掘集成

app_unifiedschema在设计时已考虑未来AI/ML消费。v_unified_batch_profile视图提供扁平化、特征丰富的数据集，适用于：

- 多变量数据分析（PCA、PLS）用于工艺理解

- 预测建模：将工艺参数轨迹与最终质量结果关联

- 异常检测：对新进批次数据进行异常识别

待条件成熟时，可新增app_mlschema用于特征工程视图和模型元数据，无需修改现有数据管道。

## 10.2 阶段路线图

- Phase 1（MVP）：FastAPI +
  React脚手架、研发LIMS趋势分析和相似性模块、基础认证

- Phase 2：QC LIMS ETL集成、放行检验模块、稳定性分析、JWT认证

- Phase 3：CPV看板及工艺数据集成、app_unified视图、Cpk/Ppk

- Phase 4：AI/ML分析、高级报告、Redis缓存、多用户RBAC

附录A：文档交付清单

本项目将产出以下文档：

- QAP-SAD-001：系统架构设计文档（本文档）

- QAP-DDM-001：数据模型详细设计（ER图、DDL、app_unified规格）

- QAP-API-001：API设计规格（OpenAPI/Swagger、请求/响应schema）

- QAP-UIA-001：UI信息架构（页面层级、线框图、组件目录）

- QAP-AMS-001：分析模块规格（算法定义、输入/输出契约）

- QAP-PCS-001：项目结构与编码规范
