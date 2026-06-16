# CMC LabOps Portal 设计文档索引

> 本目录是 CMC LabOps Portal 的设计文档集。**正式四件套**是系统现状的权威来源（需求→架构→数据模型→UI 逐层细化）；
> **特性档案**（features/）记录单个功能的设计与决策过程，功能落地后其事实已回填四件套；
> **归档**（archive/）是已完成使命的历史文档。
>
> 注：文件名统一沿用 `_V1_0` 后缀、不随版本改名；真实版本见下表与各文件头部修订记录。

## 正式四件套（权威现状，按上位→下位）

| 文档 | 编号 | 版本 | 内容 |
|---|---|---|---|
| [用户需求文档](CMC_LabOps_Portal_用户需求文档_V1_0.md) | URD-LABOPS-001 | V1.6 | 物料库存 / 仪器设备 / 统一平台三大模块需求（FR 条目 + 验收依据） |
| [架构设计文档](CMC_LabOps_Portal_架构设计文档_V1_0.md) | ARCH-LABOPS-001 | V1.5 | 系统边界、技术选型、Schema 划分、统一认证/权限/审计、部署架构 |
| [数据模型设计文档](CMC_LabOps_Portal_数据模型设计文档_V1_0.md) | DM-LABOPS-001 | V1.5 | 表结构 / DDL / 约束 / 索引（含位置树 storage_node、孔位 cell_occupancy） |
| [UI 信息架构与线框图](CMC_LabOps_Portal_UI信息架构与线框图_V1_0.md) | UI-LABOPS-001 | V1.5 | 导航、布局、各页面线框、组件规范 |

引用关系：URD（最上位）→ ARCH → DM / UI。四件套头部互标"上位/关联文档"版本号。

## 特性档案 `features/`（设计·决策过程，事实已回填四件套）

| 档案 | 落地状态 | 现状权威位置 |
|---|---|---|
| [存放位置管理增强设计](features/CMC_LabOps_Portal_存放位置管理增强设计_V1_0.md) | 已实施 | DM §3 / URD §2.2 / UI §5.2·§5.6 |
| [入库登记重构设计](features/CMC_LabOps_Portal_入库登记重构设计_V1_0.md) | 已实施 | URD §2.2 / UI §5.2 |
| [入库人姓名快照设计](features/CMC_LabOps_Portal_入库人姓名快照设计_V1_0.md) | 已实施 | DM §3.5 / URD FR-MAT-053 / UI §5.4 |
| [登录续期与会话保活设计](features/CMC_LabOps_Portal_登录续期与会话保活设计_V1_0.md) | **部分实施**（仅第 1 步自动续期上线；空闲登出/编辑防丢未做） | ARCH §5.1 / URD FR-PLT-011·014 / UI §4.1 |

## 归档 `archive/`（历史文档）

| 文档 | 说明 |
|---|---|
| [React 前端迁移方案](archive/CMC_LabOps_Portal_React前端迁移方案_V1_0.md) | Streamlit→React 迁移计划，迁移已完成、Streamlit 已退役，留作历史记录 |

## 其他

- [文档整合任务清单](文档整合任务清单.md) — 2026-06 把特性档案事实回填四件套的执行清单与代码核验表（过程记录）。
- 运维/部署见仓库根：`DEPLOY.md`（技术部署）、`服务器操作指南.md`（日常运维）、`README.md`（项目总览）、`CLAUDE.md`（操作约定）。
