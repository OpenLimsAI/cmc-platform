# AGENTS.md — cmc-water-system-dashboard

> 版本：0.7｜日期：2026-10-09。项目专属工作约定；通用要求见用户当前指令和 `/Users/qingcheng/code/AGENTS.md`。

## 项目定位

纯化水、注射用水、纯蒸汽的检验结果与趋势看板。先 Mac 开发验收，再 GitHub → Linux 发布。Hub 是唯一用户入口，MDM 是账号与角色权威源。基础应用已在 Mac/Linux 部署；以实际验收记录区分代码、服务、数据与真实身份/浏览器验收状态。

## 开始前必读

1. 通读 `/Users/qingcheng/code/AGENTS.md`、`CLAUDE.md`、`CMAB_Data_Architecture_Whitepaper_V0_4.md`、`PORTS.md`；白皮书 Draft 与历史快照须对照实际状态。
2. 本项目 `README.md`、`docs/README.md`、`docs/STATUS.md` 和 `docs/01` 至 `docs/10`；索引给出完整文件名。状态登记区分本轮核实与历史证据，旧部署/调查记录不作实时状态；未实现要求与代码差距保留在 docs/10。
3. 数据工作读 `../qc-lims-etl/README.md`、`../qc-lims-etl/docs/staging-filter-principles.md`、`../qc-lims-etl/docs/water-numeric-companion-20261001.md`、`../qc-lims-etl/docs/06-whitepaper-compliance.md`，查 `../qc-lims-etl/etl/staging.py`。
4. 认证/入口工作读 `../cmab-hub/AGENTS.md`、`../cmab-hub/nginx/README.md`、`../cmab-hub/frontend/src/shared/cmabSession.ts`，以及 `../cmab-mdm-platform/AGENTS.md`、实际认证代码。
5. 结构变更读 `../cmc-schema-migrations/README.md`、`../cmc-schema-migrations/SOP.md`，盘点消费者后走该仓库相应迁移链。

以上相对路径均以本项目根目录为基准；跨项目文件是依赖资料，不保证自动加载。Mac 绝对路径用于本地开发；Linux 按部署手册核对目标检出与对应资料。

## 核心边界

- 当前仅总览和取样点趋势两页；总览WFI/PW/PS三卡片独立统计，不继承趋势筛选。位置与系统分类待用户对照表后按新需求处理。

- 看板用只读账号查询 `cmc_analytics` 的既有 QC staging；日常请求不得直连 Oracle 或在 `cmc_gmp` 做分析扫描。ETL 和最终结果筛选规则由 qc-lims-etl 维护。
- `stg_lv_dataitem` 含中间参数；主看板使用宽表中的水系统规则。保留源结果、单位、来源键、状态、日期来源与选择规则。
- 水样按样品/取样点分析，不强求批次。业务批号如需展示，API 使用 `batch_number`；不机械改源列或内部主键。
- 数值和结论可能属于同一次检测。计数与趋势粒度按 docs/04；不能把宽表行数直接称为检测次数。
- `<1`、未检出、符合规定、空值和无法解析的值分别处理，保留原显示值；不能猜测限度、采样时间、设备或回路归属。
- 取样点映射需有权威来源和版本；设备台账取 MDM，账号角色取 MDM，不在本应用另建权威源。
- 趋势默认按 Asia/Shanghai 当前日期回溯 12 日历月，快捷范围为近 3/6/12 个月；图、表和导出共享解析后的日期与筛选，详见 docs/04/07。
- MDM 分配仅查看、查看＋导出两档权限；后端单独保护图像、表格和组合包导出。图表和原始数据表必须来自同一次取数，详见 docs/06/07。
- 后端验签、检查 access 类型、到期、临时密码和业务角色；生产或验收环境缺少验签配置应启动失败。磁贴显隐不能替代接口鉴权。
- 复用 Hub 会话母本、统一令牌键、MDM 刷新和退出；会话时长按 MDM 策略。登录和跳转使用 Hub 同源路径。
- 前后端绑定本机；固定端口核实并登记 PORTS 后使用。Hub 路径为 `/water/`。
- Python 使用 `uv`、类型标注、pathlib、logging；后端 FastAPI/SQLAlchemy/Pydantic，前端 React/TypeScript/Vite/Ant Design/React Query，图表 ECharts。优先已有依赖和简单实现。
- 写入测试用隔离环境；真实 Mac 快照保持只读。只运行相关测试，报告实际执行结果。
- 共享结构变更归 cmc-schema-migrations；没有结构变化不新增迁移。数据导入、角色配置、代码发布分别记录。
- 提交、push、部署、迁移或更改角色须在已有有效会话授权和项目流程内执行；授权持续有效时不重复要求确认。保护凭据，不在文档或日志输出连接密码或令牌。

## 交付

中文简述修改、原因、实际验证和剩余事项；分别报告文档、代码、数据、权限和部署状态。新决定写 docs/10，细节更新专项文档；AGENTS 保持稳定和简短。
