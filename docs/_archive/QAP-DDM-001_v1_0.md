# QAP-DDM-001 质量分析平台 数据模型详细设计

**Quality Analysis Platform**

**质量分析平台**

数据模型详细设计文档

QAP-DDM-001 | V1.0 | 2026-05-13

|              |             |          |            |
|--------------|-------------|----------|------------|
| **字段**     | **值**      | **字段** | **值**     |
| **文档编号** | QAP-DDM-001 | **版本** | 1.0        |
| **状态**     | 草稿        | **日期** | 2026-05-13 |
| **编制**     | CMC数据团队 | **密级** | 内部       |

# 1. 概述

## 1.1 文档目的

本文档定义质量分析平台（QAP）的完整数据模型，覆盖原始层、清洗层、维度层、应用层和配置层的所有表结构、字段定义、索引策略和数据库权限模型。

## 1.2 读者

- 后端开发人员：根据本文档编写SQLAlchemy模型和Alembic迁移

- ETL开发人员：理解staging层的目标结构，确保ETL输出与之对齐

- DBA/运维：按照权限模型配置数据库角色和访问控制

## 1.3 术语约定

- PK = 主键；FK = 外键；IDX = 已建索引；UQ = 唯一约束

- RD = 研发实验室；QC = 质量控制实验室

- LIMS = 实验室信息管理系统

- CPV = 持续工艺验证（Continued Process Verification）

# 2. 数据架构总览

## 2.1 分层架构

cmc_data_platform数据库采用五层架构，所有层在同一个数据库中通过schema隔离：

- 原始层（raw_*）：LIMS源系统的原始副本，字段名保持源系统命名（大写），不做任何转换

- 清洗层（staging_*）：清洗归一化后的数据，统一命名规范（snake_case），建立外键关系

- 维度层（meta）：跨域共享参考数据

- 应用层（app_*）：面向分析的视图和物化视图，供QAP API消费

- 配置层（qap_config）：QAP应用自身的配置数据，如分析预设和控制限

## 2.2 数据流向

原始层 → 清洗层 → 应用层 → API →前端。每一层只消费上一层的数据，不跨层访问。ETL负责原始层到清洗层的数据流转，应用层的视图直接引用清洗层和维度层。

## 2.3 跨域关联键

batch_number是跨所有数据源的天然关联键。同一批次在研发LIMS、QCLIMS和Lucullus中使用相同的批号，无需额外的mapping表。所有跨域查询（CPV、AI/ML数据挖掘）均通过batch_number进行关联。

# 3. 原始层（Raw Layer）

## 3.1 raw_rd_lims.sample

研发LIMS（SampleManager）样品表的原始抽取，共34列。数据量：16,573行。

|                        |           |          |                |
|------------------------|-----------|----------|----------------|
| **列名**               | **类型**  | **约束** | **说明**       |
| **sample_id**          | text      | PK       | 主键           |
| **PROJECT_ID**         | text      | IDX      | 项目编号       |
| **SAMPLE_NAME**        | text      |          | 样品名称       |
| **U_REMARK**           | text      |          | 备注           |
| **LOGIN_DATE**         | timestamp |          | 登录日期       |
| **CT_PRODUCTTYPE**     | text      |          | 产品类型       |
| **STAB_STUDY_ID**      | text      |          | 稳定性研究编号 |
| **STABILITY_SAMPLE**   | text      |          | 稳定性样品标识 |
| **LAYER_FACTOR**       | text      |          | 分层因子       |
| **C_FACTOR**           | text      |          | 条件因子       |
| **TIME_FACTOR**        | text      |          | 时间因子       |
| **LOGIN_BY**           | text      |          | 登录人         |
| **SAMPLED_DATE**       | timestamp |          | 取样日期       |
| **RECD_DATE**          | timestamp |          | 接收日期       |
| **ENTERED_ON**         | timestamp |          | 录入时间       |
| **ENTERED_BY**         | text      |          | 录入人         |
| **DATERESREQ**         | timestamp |          | 要求出结果日期 |
| **DATE_STARTED**       | timestamp |          | 开始日期       |
| **STARTER**            | text      |          | 启动人         |
| **GROUP_ID**           | text      |          | 组别           |
| **DATE_COMPLETED**     | timestamp |          | 完成日期       |
| **COMPLETER**          | text      |          | 完成人         |
| **DATE_AUTHORISED**    | timestamp |          | 审核日期       |
| **PRODUCT**            | text      |          | 产品           |
| **CT_SMP_ON**          | timestamp |          | 取样时间       |
| **CT_SAMPLINGPERSON**  | text      |          | 取样人         |
| **DESCRIPTION**        | text      |          | 描述           |
| **U_COA_MLP**          | text      |          | CoA/MLP标识    |
| **STATUS**             | text      |          | 状态           |
| **LOCATION_ID**        | text      |          | 位置标识       |
| **U_GROUPLEAD_ON**     | timestamp |          | 组长确认时间   |
| **U_PERSION_ON**       | timestamp |          | 个人确认时间   |
| **CT_TESTTYPE**        | text      |          | 检测类型       |
| **PRODUCTION_LINE_ID** | text      |          | 生产线标识     |
| **TIMEPOINT**          | numeric   |          | 稳定性时间点   |
| **TIMEPOINT_UNIT**     | text      |          | 时间点单位     |

## 3.2 raw_rd_lims.test

研发LIMS检测任务表的原始抽取，共25列。数据量：37,129行。

|                          |           |          |                        |
|--------------------------|-----------|----------|------------------------|
| **列名**                 | **类型**  | **约束** | **说明**               |
| **test_id**              | text      | PK       | 主键                   |
| **sample_id**            | text      | FK/IDX   | 关联raw_rd_lims.sample |
| **TEST_NUMBER**          | text      |          | 检测编号               |
| **ANALYSIS**             | text      |          | 分析方法               |
| **STATUS**               | text      |          | 样品级状态             |
| **STATUS_test**          | text      |          | 检测级状态             |
| **TEST_COUNT**           | text      |          | 检测计数               |
| **COMPONENT_LIST**       | text      |          | 组分列表               |
| **DATE_STARTED_test**    | timestamp |          | 检测开始时间           |
| **STARTER_test**         | text      |          | 检测启动人             |
| **GROUP_ID_test**        | text      |          | 检测组别               |
| **DATE_COMPLETED_test**  | timestamp |          | 检测完成时间           |
| **COMPLETER_test**       | text      |          | 检测完成人             |
| **DATE_AUTHORISED_test** | timestamp |          | 检测审核时间           |
| **AUTHORISER**           | text      |          | 样品级审核人           |
| **AUTHORISER_test**      | text      |          | 检测级审核人           |
| **U_ANALDESC**           | text      |          | 分析描述               |
| **SAMPLE**               | text      |          | 样品标识               |
| **U_GROUPLEAD_ON**       | timestamp |          | 组长确认时间           |
| **U_PERSON_ON**          | timestamp |          | 个人确认时间           |
| **U_PERSION_BY**         | text      |          | 个人确认人             |
| **GROUP_ID**             | text      |          | 组别                   |
| **DATE_STARTED**         | timestamp |          | 样品级开始时间         |
| **DATE_COMPLETED**       | timestamp |          | 样品级完成时间         |
| **DATE_AUTHORISED**      | timestamp |          | 样品级审核时间         |

## 3.3 raw_rd_lims.result

研发LIMS检测结果表的原始抽取，共15列。数据量：125,446行。

|                     |           |          |                      |
|---------------------|-----------|----------|----------------------|
| **列名**            | **类型**  | **约束** | **说明**             |
| **result_id**       | text      | PK       | 主键                 |
| **test_id**         | text      | FK/IDX   | 关联raw_rd_lims.test |
| **NAME**            | text      |          | 属性名称             |
| **RESULT_TYPE**     | text      |          | 结果类型             |
| **RAW_RESULT**      | text      |          | 原始结果             |
| **VALUE**           | text      |          | 结果值（文本）       |
| **TEXT**            | text      |          | 文本内容             |
| **UNITS**           | text      |          | 单位                 |
| **ENTERED_ON**      | timestamp |          | 录入时间             |
| **ENTERED_BY**      | text      |          | 录入人               |
| **ORDER_NUMBER**    | text      |          | 排序号               |
| **STATUS**          | text      |          | 状态                 |
| **DATE_AUTHORISED** | timestamp |          | 审核日期             |
| **TEST_NUMBER**     | text      |          | 检测编号             |
| **AUTHORISER**      | text      |          | 审核人               |

## 3.4 raw_qc_lims（待建）

QC LIMS（LabVantage）的原始层表结构将在QCETL打通后建立。预计包含与raw_rd_lims对等的sample、test、result三表，但字段名和编码规则将根据LabVantage的实际schema确定。

## 3.5 raw_bioprocess（已有，Linux VM）

Lucullus生物反应器数据的原始层已在LinuxVM上建立，包含时序信号数据。详细字段待从Linux VM确认后补充。

# 4. 清洗层（Staging Layer）

## 4.1 设计原则

- 字段名统一为snake_case，消除源系统的大写命名差异

- 时间字段统一为timestamp类型，命名以_dt后缀结尾

- 数值型结果从text转为numeric（value_num），同时保留原始文本（value_str）

- 建立外键关系：result_clean → test_clean → sample_clean

- QC
  LIMS的staging_qc表采用与staging_rd完全镜像的结构，确保两套系统的数据可通过UNION  ALL直接合并

## 4.2 staging_rd.sample_clean

研发LIMS样品清洗表。数据量与raw_rd_lims.sample一致。

|                        |           |          |                                   |
|------------------------|-----------|----------|-----------------------------------|
| **列名**               | **类型**  | **约束** | **说明**                          |
| **sample_id**          | text      | PK       | 样品唯一标识，来源于SampleManager |
| **project_id**         | text      |          | 项目编号，关联meta.dim_project    |
| **sample_name**        | text      |          | 样品名称                          |
| **request_dt**         | timestamp |          | 送样/请求日期                     |
| **request_person**     | text      |          | 送样人                            |
| **sampled_dt**         | timestamp |          | 取样日期                          |
| **received_dt**        | timestamp |          | 接收日期                          |
| **status**             | text      |          | 样品状态（A=已授权, I=进行中等）  |
| **batch_number**       | text      | IDX      | 批号，跨系统关联的天然键          |
| **sample_type**        | text      |          | 样品类型（原料药、制剂等）        |
| **test_type**          | text      |          | 检测类型（放行、稳定性、表征等）  |
| **started_dt**         | timestamp |          | 检测开始时间                      |
| **tester**             | text      |          | 检测人                            |
| **completed_dt**       | timestamp |          | 检测完成时间                      |
| **completer**          | text      |          | 完成人                            |
| **authorised_dt**      | timestamp |          | 审核日期                          |
| **authoriser**         | text      |          | 审核人                            |
| **group_id**           | text      |          | 组别标识                          |
| **production_line_id** | text      | IDX      | 生产线标识                        |
| **timepoint**          | numeric   | IDX      | 稳定性时间点                      |
| **timepoint_unit**     | text      |          | 时间点单位（M=月, W=周等）        |

索引：project_id, status, received_dt, request_dt, batch_number,production_line_id, timepoint

## 4.3 staging_rd.test_clean

研发LIMS检测任务清洗表。

|                             |           |          |                                   |
|-----------------------------|-----------|----------|-----------------------------------|
| **列名**                    | **类型**  | **约束** | **说明**                          |
| **test_id**                 | text      | PK       | 检测任务唯一标识                  |
| **sample_id**               | text      | FK       | 关联sample_clean.sample_id        |
| **method_code**             | text      | IDX      | 检测方法代码，关联meta.dim_method |
| **method_name**             | text      |          | 检测方法名称（冗余，便于查询）    |
| **started_dt**              | timestamp |          | 检测开始时间                      |
| **groupleader_received_dt** | timestamp |          | 组长接收时间                      |
| **assigned_dt**             | timestamp |          | 分配时间                          |
| **tester**                  | text      | IDX      | 检测人员                          |
| **status**                  | text      | IDX      | 检测状态                          |
| **completed_dt**            | timestamp | IDX      | 完成时间                          |
| **authorised_dt**           | timestamp | IDX      | 审核时间                          |
| **authoriser**              | text      |          | 审核人                            |
| **group_id**                | text      |          | 所属组别                          |

索引：sample_id, status, method_code, tester, completed_dt,authorised_dt

外键：sample_id REFERENCES staging_rd.sample_clean(sample_id)

## 4.4 staging_rd.result_clean

研发LIMS检测结果清洗表。

|                          |           |          |                                          |
|--------------------------|-----------|----------|------------------------------------------|
| **列名**                 | **类型**  | **约束** | **说明**                                 |
| **result_id**            | text      | PK       | 结果唯一标识                             |
| **test_id**              | text      | FK       | 关联test_clean.test_id                   |
| **attribute**            | text      | IDX      | 检测属性名称（如Purity(SEC)、Potency等） |
| **order_no**             | text      |          | 结果排序号                               |
| **result_entered_dt**    | timestamp |          | 结果录入时间                             |
| **result_authorised_dt** | timestamp |          | 结果审核时间                             |
| **authoriser**           | text      |          | 审核人                                   |
| **value_num**            | numeric   |          | 数值型结果（用于统计计算）               |
| **result_type**          | text      | IDX      | 结果类型                                 |
| **value_str**            | text      |          | 文本型结果（如符合、通过等）             |
| **unit**                 | text      |          | 单位                                     |
| **judgement**            | text      |          | 判定结果                                 |
| **updated_at**           | timestamp |          | 最近更新时间（ETL水位线用）              |

索引：test_id, attribute, result_type

外键：test_id REFERENCES staging_rd.test_clean(test_id)

## 4.5 staging_qc（规划中，镜像staging_rd）

QCLIMS清洗层采用与staging_rd完全相同的表结构和字段命名。以下以sample_clean_qc为例展示：

|                        |           |          |                                  |
|------------------------|-----------|----------|----------------------------------|
| **列名**               | **类型**  | **约束** | **说明**                         |
| **sample_id**          | text      | PK       | 样品唯一标识，来源于LabVantage   |
| **project_id**         | text      |          | 项目编号，关联meta.dim_project   |
| **sample_name**        | text      |          | 样品名称                         |
| **request_dt**         | timestamp |          | 送样/请求日期                    |
| **request_person**     | text      |          | 送样人                           |
| **sampled_dt**         | timestamp |          | 取样日期                         |
| **received_dt**        | timestamp |          | 接收日期                         |
| **status**             | text      | IDX      | 样品状态                         |
| **batch_number**       | text      | IDX      | 批号（与研发LIMS相同的批号体系） |
| **sample_type**        | text      |          | 样品类型                         |
| **test_type**          | text      |          | 检测类型（放行、稳定性等）       |
| **started_dt**         | timestamp |          | 检测开始时间                     |
| **tester**             | text      |          | 检测人                           |
| **completed_dt**       | timestamp |          | 检测完成时间                     |
| **completer**          | text      |          | 完成人                           |
| **authorised_dt**      | timestamp |          | 审核日期                         |
| **authoriser**         | text      |          | 审核人                           |
| **group_id**           | text      |          | 组别标识                         |
| **production_line_id** | text      | IDX      | 生产线标识                       |
| **timepoint**          | numeric   | IDX      | 稳定性时间点                     |
| **timepoint_unit**     | text      |          | 时间点单位                       |

staging_qc.test_clean和staging_qc.result_clean的结构与staging_rd中对应表完全一致，仅sample_id来源不同（LabVantage）。

这种镜像设计的核心价值在于：app_unified层可以通过简单的UNIONALL合并两套LIMS数据，无需复杂的字段映射逻辑。

# 5. 维度层（Meta Schema）

## 5.1 meta.dim_project

|                  |          |          |                                       |
|------------------|----------|----------|---------------------------------------|
| **列名**         | **类型** | **约束** | **说明**                              |
| **project_id**   | text     | PK       | 项目编号，如CMAB001                   |
| **project_name** | text     |          | 项目名称                              |
| **project_type** | text     |          | 项目类型（单抗、双抗、ADC、融合蛋白） |

待扩展字段（Phase 2）：product_name, molecule_type, development_phase,therapeutic_area, ind_status

## 5.2 meta.dim_method

|                 |          |          |                      |
|-----------------|----------|----------|----------------------|
| **列名**        | **类型** | **约束** | **说明**             |
| **method_code** | text     | PK       | 方法代码             |
| **method_name** | text     |          | 方法名称             |
| **std_minutes** | integer  |          | 标准检测时间（分钟） |
| **target_days** | integer  |          | 目标完成天数         |

## 5.3 meta.dim_employee

|                   |          |          |          |
|-------------------|----------|----------|----------|
| **列名**          | **类型** | **约束** | **说明** |
| **employee_id**   | text     | PK       | 员工编号 |
| **employee_name** | text     |          | 员工姓名 |
| **department**    | text     |          | 所属部门 |

## 5.4 meta.etl_watermark

ETL增量抽取水位线表，每个ETL任务一行。

|                          |           |          |                                     |
|--------------------------|-----------|----------|-------------------------------------|
| **列名**                 | **类型**  | **约束** | **说明**                            |
| **job_name**             | text      | PK       | ETL任务名称                         |
| **source_system**        | text      | NOT NULL | 源系统标识                          |
| **target_table**         | text      | NOT NULL | 目标表名                            |
| **last_success_ts**      | timestamp |          | 上次成功抽取时间戳                  |
| **last_run_started_at**  | timestamp |          | 上次运行开始时间                    |
| **last_run_finished_at** | timestamp |          | 上次运行结束时间                    |
| **last_run_status**      | text      |          | 上次运行状态                        |
| **last_run_message**     | text      |          | 上次运行消息                        |
| **updated_at**           | timestamp | NOT NULL | 记录更新时间，默认CURRENT_TIMESTAMP |

## 5.5 meta.dim_attribute（新增）

属性标准化字典表，解决两套LIMS中相同检测项可能使用不同名称的问题（如一套叫Purity(SEC)，另一套叫SEC_Purity）。这是AI/ML数据挖掘的前提条件。

|                        |          |          |                                      |
|------------------------|----------|----------|--------------------------------------|
| **列名**               | **类型** | **约束** | **说明**                             |
| **attribute_id**       | serial   | PK       | 自增主键                             |
| **source_system**      | text     | NOT NULL | 来源系统（RD_LIMS / QC_LIMS）        |
| **source_attribute**   | text     | NOT NULL | 原始属性名（如LIMS中的NAME字段值）   |
| **std_attribute**      | text     | NOT NULL | 标准化属性名（如Purity_SEC）         |
| **attribute_category** | text     |          | 属性分类（纯度、效价、残留、理化等） |
| **display_name**       | text     |          | 前端显示名称                         |
| **default_unit**       | text     |          | 默认单位                             |
| **is_numeric**         | boolean  |          | 是否为数值型属性                     |
| **sort_order**         | integer  |          | 排序权重                             |

用法示例：app_unified视图在合并两套LIMS结果时，通过LEFT JOINmeta.dim_attribute将source_attribute映射为std_attribute，实现属性名的统一。初始数据需通过枚举现有result_clean.attribute的DISTINCT值来填充。

# 6. 应用层（App Layer）

## 6.1 app_rd（现有视图）

Linux VM上已有以下视图（Mac上尚未同步）：

- v_sample_overview：样品总览，关联项目维度

- v_completed_tests：已完成检测任务汇总

- v_pending_tests：待检测任务

- v_test_task_monitor：检测任务监控

- v_daily_workload：每日工作量统计

- v_overdue_snapshot：超期快照

- v_turnaround：周转时间分析

这些视图服务于实验室运营监控模块，在新架构中继续保留使用。

## 6.2 app_qc（待建）

QC分析视图将在staging_qc数据就绪后建立。预期视图包括：

- v_release_batch_summary：批放行检验汇总，每批次一行，包含所有检测项及判定结果

- v_qc_trend_data：QC趋势分析宽表，按属性+批次聚合，供趋势控制图使用

- v_qc_stability_data：QC稳定性数据视图，按研究+时间点+属性组织

## 6.3 app_unified（新增，核心）

跨域统一层是本次数据模型设计的核心创新。它通过视图合并两套LIMS的质量数据与工艺参数，消除数据孤岛。

|                          |                |                                                    |
|--------------------------|----------------|----------------------------------------------------|
| **视图名**               | **类型**       | **说明**                                           |
| v_unified_batch          | 普通视图       | 主批次维度，跨两套LIMS和工艺数据的batch_number合并 |
| v_unified_quality_result | 普通视图       | 所有质量结果的统一视图，归一化为统一结构           |
| v_unified_batch_profile  | 物化视图(建议) | 透视视图，合并工艺参数和质量属性，每批次一行       |

### 6.3.1 v_unified_quality_result 视图定义

该视图通过UNIONALL合并staging_rd和staging_qc的三表JOIN结果，归一化为统一输出结构：

> SELECT
>
> s.batch_number,
>
> s.project_id,
>
> COALESCE(da.std_attribute, r.attribute) AS attribute,
>
> r.value_num,
>
> r.value_str,
>
> r.unit,
>
> t.method_code,
>
> t.completed_dt AS test_date,
>
> s.sample_type,
>
> s.test_type,
>
> s.timepoint,
>
> s.timepoint_unit,
>
> 'RD_LIMS' AS source_system
>
> FROM staging_rd.sample_clean s
>
> JOIN staging_rd.test_clean t ON t.sample_id = s.sample_id
>
> JOIN staging_rd.result_clean r ON r.test_id = t.test_id
>
> LEFT JOIN meta.dim_attribute da
>
> ON da.source_system = 'RD_LIMS'
>
> AND da.source_attribute = r.attribute
>
> UNION ALL
>
> -- staging_qc部分结构完全对称，source_system = 'QC_LIMS'

该视图是所有跨域分析的数据入口。前端通过data_source参数选择RD/QC/ALL时，API层根据选择决定查询staging_rd/staging_qc/app_unified。

### 6.3.2 v_unified_batch_profile 物化视图

该视图将质量属性和工艺参数合并为每批次一行的宽表，是CPV看板和AI/ML数据挖掘的核心数据源。建议实现为物化视图（MATERIALIZEDVIEW）并定期刷新，因其涉及多表聚合和透视操作。

结构概要：

- batch_number, project_id, product_name：批次标识

- purity_sec, purity_cex_main, potency,
  ...：质量属性列（来自v_unified_quality_result的透视）

- temp_mean, temp_sd, ph_mean, ph_sd, do_mean,
  ...：工艺参数统计列（来自staging_bioprocess的聚合）

- source_systems：数据来源标记（数组，如['RD_LIMS','QC_LIMS']）

透视列的具体定义取决于dim_attribute表中的属性目录和实际工艺参数列表，将在数据填充后具体实现。

# 7. 配置层（qap_config Schema）

配置层是QAP应用自身的持久化存储，不涉及LIMS数据。使用独立schema与分析数据隔离。

## 7.1 qap_config.analysis_preset

分析预设表，保存用户自定义的分析配置（项目+属性+参数组合），支持一键加载。

|                 |           |          |                                                  |
|-----------------|-----------|----------|--------------------------------------------------|
| **列名**        | **类型**  | **约束** | **说明**                                         |
| **preset_id**   | serial    | PK       | 自增主键                                         |
| **preset_name** | text      | NOT NULL | 预设名称（如SEC纯度趋势-CMAB001）                |
| **module**      | text      | NOT NULL | 分析模块（trend / similarity / stability / cpv） |
| **config_json** | jsonb     | NOT NULL | 完整过滤+参数配置JSON                            |
| **created_by**  | text      |          | 创建人                                           |
| **created_at**  | timestamp | NOT NULL | 创建时间                                         |
| **updated_at**  | timestamp | NOT NULL | 更新时间                                         |

## 7.2 qap_config.control_limits

控制限表，存储质量属性的标准限、行动限和警戒限。支持按项目和有效期管理。

|                    |          |          |                                                 |
|--------------------|----------|----------|-------------------------------------------------|
| **列名**           | **类型** | **约束** | **说明**                                        |
| **limit_id**       | serial   | PK       | 自增主键                                        |
| **project_id**     | text     |          | 项目编号（NULL=全局适用）                       |
| **attribute**      | text     | NOT NULL | 属性名（标准化后）                              |
| **spec_lower**     | numeric  |          | 标准下限                                        |
| **spec_upper**     | numeric  |          | 标准上限                                        |
| **action_lower**   | numeric  |          | 行动限下限                                      |
| **action_upper**   | numeric  |          | 行动限上限                                      |
| **alert_lower**    | numeric  |          | 警戒限下限                                      |
| **alert_upper**    | numeric  |          | 警戒限上限                                      |
| **source**         | text     |          | 来源（registered_spec / internal / calculated） |
| **effective_from** | date     |          | 生效日期                                        |
| **effective_to**   | date     |          | 失效日期                                        |

# 8. 数据库权限模型

## 8.1 角色定义

- etl_rd_user：研发LIMS
  ETL专用，对raw_rd_lims和staging_rd有INSERT/UPDATE/DELETE权限

- etl_qc_user：QC LIMS
  ETL专用，对raw_qc_lims和staging_qc有INSERT/UPDATE/DELETE权限

- qap_reader：QAP后端只读用户，对staging_*、meta、app_*有SELECT权限

- qap_writer：QAP后端读写用户，对qap_config有ALL权限（用于保存配置）

- dba_admin：管理员角色，拥有所有权限

## 8.2 权限矩阵

|             |               |                |                |                      |
|-------------|---------------|----------------|----------------|----------------------|
| **Schema**  | **ETL用户**   | **qap_reader** | **qap_writer** | **说明**             |
| raw_rd_lims | INSERT/UPDATE | —              | —              | 仅ETL写入            |
| raw_qc_lims | INSERT/UPDATE | —              | —              | 仅ETL写入            |
| staging_rd  | INSERT/UPDATE | SELECT         | —              | ETL写入，QAP可读     |
| staging_qc  | INSERT/UPDATE | SELECT         | —              | ETL写入，QAP可读     |
| meta        | INSERT/UPDATE | SELECT         | —              | 维度数据，QAP可读    |
| app_rd      | —             | SELECT         | —              | 视图，QAP可读        |
| app_qc      | —             | SELECT         | —              | 视图，QAP可读        |
| app_unified | —             | SELECT         | —              | 跨域视图，QAP可读    |
| qap_config  | —             | SELECT         | ALL            | QAP配置表，QAP可读写 |

## 8.3 创建脚本示例

> -- 创建只读角色
>
> CREATE ROLE qap_reader LOGIN PASSWORD '***';
>
> GRANT USAGE ON SCHEMA staging_rd, staging_qc, meta,
>
> app_rd, app_qc, app_unified TO qap_reader;
>
> GRANT SELECT ON ALL TABLES IN SCHEMA staging_rd,
>
> staging_qc, meta, app_rd, app_qc, app_unified TO qap_reader;
>
> -- 创建配置读写角色
>
> CREATE ROLE qap_writer LOGIN PASSWORD '***';
>
> GRANT USAGE ON SCHEMA qap_config TO qap_writer;
>
> GRANT ALL ON ALL TABLES IN SCHEMA qap_config TO qap_writer;
>
> GRANT USAGE ON ALL SEQUENCES IN SCHEMA qap_config TO qap_writer;

# 9. 索引策略

## 9.1 现有索引

staging_rd的三表已建立充分的索引，覆盖主要查询路径：

- sample_clean：project_id, status, received_dt, request_dt,
  batch_number, production_line_id, timepoint

- test_clean：sample_id, status, method_code, tester, completed_dt,
  authorised_dt

- result_clean：test_id, attribute, result_type

## 9.2 建议新增索引

针对QAP高频查询场景，建议补充以下索引：

- staging_rd.result_clean: 复合索引 (test_id, attribute) ——
  支持按检测任务+属性的高频查询

- staging_qc各表：建立与staging_rd镜像的索引集

- meta.dim_attribute: (source_system, source_attribute) 唯一约束 ——
  防止重复映射

- qap_config.control_limits: (project_id, attribute) ——
  支持按项目+属性的控制限查询

## 9.3 物化视图刷新策略

v_unified_batch_profile建议使用MATERIALIZED VIEW + REFRESHCONCURRENTLY（需在视图上建UNIQUEINDEX）。刷新频率与ETL同步，在每次ETL完成后触发：

> REFRESH MATERIALIZED VIEW CONCURRENTLY
> app_unified.v_unified_batch_profile;

# 10. 待办事项

- LabVantage字段映射：需获取QC
  LIMS的原始字段列表，完成staging_qc的ETL字段映射

- dim_attribute初始数据：枚举现有staging_rd.result_clean.attribute的DISTINCT值，建立初始映射

- dim_project扩展：确认是否需要添加product_name、molecule_type、development_phase等字段

- staging_bioprocess字段确认：需从Linux
  VM确认batch_number字段名和时间字段名

- app_bioprocess聚合视图：设计生物工艺时序数据的批次级聚合逻辑

- v_unified_batch_profile具体DDL：待dim_attribute和bioprocess字段确认后编写

- Alembic迁移脚本：根据本文档生成初始化迁移

附录A：ER关系图说明

以下为core关系链的文字描述（正式ER图见附件或在线协作工具）：

**staging_rd / staging_qc 三表关系：**

> sample_clean (1) ──\< test_clean (N)
>
> test_clean (1) ──\< result_clean (N)

**维度关联：**

> sample_clean.project_id ──\> meta.dim_project.project_id
>
> test_clean.method_code ──\> meta.dim_method.method_code
>
> result_clean.attribute ──\> meta.dim_attribute.source_attribute

**跨域关联（app_unified）：**

> staging_rd.sample_clean.batch_number
>
> = staging_qc.sample_clean.batch_number
>
> = staging_bioprocess.*.batch_number

所有跨域JOIN均通过batch_number实现，不依赖任何额外mapping表。

附录B：命名规范

- Schema命名：raw_{source} / staging_{source} / app_{source} / meta /
  qap_config

- 表命名：snake_case，清洗层加_clean后缀

- 列命名：snake_case，时间字段以_dt后缀，标识字段以_id后缀

- 视图命名：v_前缀，物化视图mv_前缀

- 索引命名：idx_{table}_{column(s)}

- 外键命名：fk_{child_table}_{parent_table}
