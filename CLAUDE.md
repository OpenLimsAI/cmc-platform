# CLAUDE.md

## 项目状态（2026-09-16 实码与数据库复核）

这是已有项目续建。已有 FastAPI/SQLAlchemy 后端、React/Ant Design/Vite 前端。放行页已按旧看板恢复左侧筛选、七类指标组合、趋势/分组均值并排图和统计汇总，新增筛选已接后端。稳定性页已接通只读API、级联筛选、逐批观察/组均值SD/逐批拟合/组拟合及来源明细；按样品、类别、方法和单位分开，缺失单位只显示原始观察，不补入放行零点。相似性页面仍占位。当前为单项目、单来源分析，可切换RD及共享staging中的QC历史记录（不含旧Excel和完整GMP快照）；详见 docs/QAP-DATA-SOURCES-001.md。研究/储存条件、历史参考、单位/规格及业务统计口径尚未验收；详见 docs/QAP-STABILITY-001.md。

现已完成 batch_number 前后端适配、XLSX 结构预览接口/页面、MDM 登录会话及验签/角色守卫代码。真实 MDM 配置与角色联调尚未验收；正式导入、员工审计入库及质量事实层尚未实现。不能把设计目标写成现成功能。

2026-09-16负责人已创建 GitHub 仓库并授权首次提交和推送：git@github.com:qingcheng81/cmc-quality-analytics-platform.git。保留全部工作，不 reset/clean，不提交密钥、上传文件、业务数据或备份。Mac 已有试用/历史数据，不能按空库重建。

## 权威与本轮交付

公司依据：父级 AGENTS.md、CLAUDE.md、`../CMAB_Data_Architecture_Whitepaper_V0_4.md`（含 D13）及修订清单。结构统一经 `../cmc-schema-migrations/`，读取其 README/SOP 后准备迁移。

本项目当前设计为 **V2.1 评审稿**，为保持链接沿用 v2_0 文件名：

- `docs/QAP-DDM-001_v2_0.md`：详细对象、字段、单位/规格/导入版本设计。
- `docs/QAP-SAD-001_v2_0.md`：现状与目标组件、MDM/门户及部署。
- `docs/QAP-DB-IMPLEMENTATION-001.md`：中央迁移草案拆分、验证、备份/回退和待确认问题。
- `docs/QAP-DB-REVIEW-20260916.md`：本轮本机只读证据及 Linux 交接快照边界。

更新前 V2.0 已保留在 docs/_archive，不再作为当前指令；旧“只有docs、纯只读无写入/迁移、Linux Docker、dim全未建”等描述失效。增量开发见 docs/QAP-DEV-LOG-20260916.md 和 docs/QAP-LOCAL-DEV.md。新表与正式保存/确认API尚未实施；当前仅有不持久化的结构预览API。

## 已确定的架构约定

- 数据库继续用 `cmc_analytics`。分析查询用真实最小权限 reader；Excel 独立受控写入新增候选/事实/meta，对共享 LIMS staging、raw 和 MDM 权威数据无写入权。
- 业务批号统一 `batch_number`，目标 VARCHAR(32)，沿用原值，不加同义 batch_id、不造 global_batch_id/crosswalk。当前仓储/接口/前端已统一 batch_number；未来部署需前后端同时更新，未登记外部消费者另核；其他系统内部数字 batch_id 和 raw 源字段保留，禁止机械替换。超长/缺失源批号保留原值并阻断相关发布，不截断。
- 复用既有 stg_sample/stg_test/stg_result；不因新质量层改名/删除它们。新字典在 dim，新事实在 mart，导入/文件/校验/血缘/审计在 meta。旧 quality 表只作兼容保留，不能冒充正式模型。
- 方法复用 dim.method_master(method_code)，没有 method_id。dim.employee_master 是 LIMS 业务人员，不是登录账号。设备台账权威是 MDM eqp，dim.equipment_master 只作采集映射。
- 员工身份和角色来自 MDM；按父级总纲前端同源会话、后端验签，操作人存 username/full_name 快照，不自建用户/密码。
- 2026-09-16负责人已确认并在Mac MDM建立两个角色：QC综合（QAP_QC_GENERAL）可查看及导入Excel，QA放行（QAP_QA_RELEASE）仅查看。当前QC只有已实现的结构预览能力，正式导入尚未开放；QA无上传/确认/更正/审批权限。尚未分配员工，项目/部门范围仍待确认。QAP配置已对齐，不能再把这两个角色定义记为待确认。
- 规格、单位、来源批准状态和复测取舍不得猜测。现有 Python/CSV 只作核对材料，不自动种入 approved 规则。
- GMP 走 snap_gmp，不能直接查询 cmc_gmp 做分析。当前快照链未在本项目验收。

## 环境与迁移

Mac PostgreSQL 为 Docker，Linux 为原生 PostgreSQL 16。rd_pg:5432 包含 cmc_analytics；MDM Mac:15432 / Linux:5433。QAP 端口8040/5140，按 ../PORTS.md 固定，禁止漂移。

Mac 当前 revision=cmc_analytics_qad_phase1，已存在84757条旧质量记录和14条导入历史（计数仅2026-09-16快照）。一期迁移文件在中央仓库尚未提交，不能删改已应用历史，也不能未经审核直接向Linux执行。Linux正式/培训版本来自同日交接，实施前重核。

培训库复用正式迁移链，但 rd-batch-registry 本地重置脚本会整库复制正式数据、换库；Linux定时任务实际状态待查。QAP接入前必须协调数据/文件/账号隔离及维护窗口，不能当普通空测试库使用。

**2026-09-16 最新授权：负责人已允许将当前 Mac 开发成果提交并推送至上述 GitHub 仓库；继续在 Mac 开发测试，Linux 部署仍须另行确认。** 本机建表、授权和数据迁移仍按原要求单独确认。最终部署路径为 Linux `/opt/cmc-quality-analytics-platform` + systemd。Linux另一套 `/opt/quality-analysis-platform` 不得擅自覆盖或混用。

## 工作方式与授权边界

用中文简洁沟通。负责人已要求继续按方案开发，当前可进行常规代码开发、只读核查、文档和迁移草案准备；执行建表、授权、数据迁移或生产部署前，展示具体diff/范围、影响、备份和回退方案，再请求负责人确认。不要输出密码，不下载Linux业务数据到Mac，除非另获明确授权。

业务代码保持现有栈，正式模型优先SQLAlchemy ORM和参数化查询；不在应用启动时create_all，不另建共享库迁移链。新契约响应使用batch_number；兼容适配前盘点消费者。所有“已验证”声明必须注明实际证据，旧算法对照测试不能代替统计业务验证。

## 第一表输入修订

负责人要求按现有Excel字段修正本项目。新增默认qap_first_table_v1结构预览契约（英文第5行/中文第6行/数据第7行），完整十维原名保留，五列草案仅兼容；DDM已补明确placement_status等来源维度。解析器v2已使真实完整15个文件均产生预览；部分源表仍有数值型批号、Excel错误或表头问题，持久导入及Excel历史读取尚未完成，不能声称已接通看板。详见docs/QAP-FIRST-TABLE-COMPATIBILITY-20260916.md。

## Excel 历史查看接入代码

已增加 EXCEL 独立来源、quality.quality_data ORM读取及放置状态筛选/分面代码；只读账号尚未获授权，当前返回读取未就绪，不能声称真实Excel历史图表已经可用。专用 qap_reader Mac 权限及回退评审包见 docs/QAP-MAC-READER-APPROVAL-20260916.md，须负责人确认后经中央迁移实施。未向 lims_admin 扩权，也未修改旧看板 qad_reader。


## Mac只读授权完成（2026-09-16最终状态）

负责人确认后，中央迁移已升级cmc_analytics_qap_reader，本项目连接切换专用qap_reader，四表SELECT和无业务写入权限验证通过。Excel历史19项目84757条已接通：放行22067、稳定性62690。全部项目API计数一致，单批SEC20条逐条对账，两页浏览器图形已验证；RD197/QC21项目正常。此前“quality无权限/Excel未接通”已解除。无业务数据修改、旧看板变更、push或Linux操作；正式导入、单位/规格及MDM员工联调仍待完成。备份、默认PUBLIC权限边界及证据见docs/QAP-MAC-READER-APPROVAL-20260916.md（docs内使用同目录文件）。

## 放行原值统计补齐

本日第十二批已为EXCEL放行恢复同项同条件的原值描述统计及当前/历史SD参考，不因缺单位一律屏蔽。不作百分比换算；旧质量标准只显示候选原限度及来源，未批准，不画有效标准线或计算能力。稳定性/QC staging规则未改。详见docs/QAP-RELEASE-PARITY-20260916.md。

## 稳定性后续补齐

稳定性已改为筛选后自动更新，补齐旧版调色板、拟合原始点开关、SD开关、截距和分时间点统计表。EXCEL时间单位明确时可按存储原值计算描述统计与OLS；结果单位仍未确认，不换算，不启用规格/等效性判断。RD/QC缺单位限制保持。Day-0配对、参比组、LME/TOST、导出等差异见docs/QAP-STABILITY-001.md，尚未宣称全面验收。此批只在Mac修改代码，未改库、推送或部署。

## 相似性描述比较已接入

相似性页面已替换占位，实现只读API、参比/比较产线显式选择、自动分析、六图结构及旧版色序、描述统计及来源明细。经本次复核，不能称新旧全面对齐：已修正散点/范围条/轴域/组序等显示差异，左栏来源语义与级联仍不同；TOST/Tier1/Tier2判定、CI、报告导出尚未接入。旧版存在CI置信度、差值方向与Tier判定矛盾，不能直接复制为正式规则。不把探索3SD带当等效标准，不调用旧LME。详见docs/QAP-SIMILARITY-001.md及docs/QAP-SIMILARITY-PARITY-AUDIT-20260916.md。本批未改库、提交、推送或部署。

## 相似性统计层缺陷修正

负责人要求先修新版错误后，已修正CI/alpha、明确比较减参比的业务入口、pooled/Welch真实计算和BF阈值、Tier1共享一次结果、显式手动delta、完整精度及Unknown状态。独立专项42项、含统计doctest全量253项通过。旧TOST/Tier golden测试已由独立验证替代；其他回归保留。当前页面仍未接入推断统计，不能声称已经出现CI或正式判定。详见docs/QAP-SIMILARITY-STATISTICS-FIX-20260916.md。本批无数据库、旧项目、Linux、提交或推送操作。
