# 交接说明（新窗口从这里开始）

**先读 `CLAUDE.md`**：项目全貌、页面结构、数据在哪怎么连、治理规矩、数据模型、上线方式都在那。
本文件只写「现在做到哪了 / 谁是谁 / 别踩什么坑」，不重复 CLAUDE.md 的内容。

## 现在是什么状态（2026-09-11）

已经是**在用的生产系统**，不是骨架了。正式入口 **http://172.19.0.105:5100/usp**（统一门户 cmab-hub 下的 `/usp`）。

- **看板**：一页四层——左栏选批次（项目→年份→批号→罐），右栏板块开关（生长曲线 / 生化曲线 / 血气 / 工艺按时段 / 工艺全量时序 / 数据表 / 取样明细），可同屏多开、多批次叠加。
- **数据录入**（`/usp/entry`，顶栏按钮进出）：本看板**唯一会写库**的功能。按日期列出当天该取样的全部样品，试验员填**渗透压**和**葡萄糖**（试剂盒法，当天没做生化分析时才填）。
- **登录**：走公司统一认证（MDM Portal 发 JWT，本地验签），见总纲 `~/code/CLAUDE.md` §8。本地不配密钥 = 开放模式，不用登录。

## 项目里的东西

- `backend/` —— FastAPI，接口分五组：`signals`（工艺时序 / 通道字典）、`vicell`（细胞）、`nova`（生化 + 血气 + 人工指标合并）、`overview`（批次总名单 / 数据表）、`manual`（数据录入，唯一写入点）、`auth`。
- `frontend/` —— Next.js 16，`basePath=/usp`。组件分工见 CLAUDE.md「技术栈」一节。
- `deploy.sh` —— **Linux 上一键部署**：拉代码 → `uv sync` → `npm ci && npm run build` → 重启 systemd（`cmc-usp-backend` / `cmc-usp-frontend`）→ 健康检查。
- `docs/etl-batch-dim-prompt.md` —— 历史文档（`mart.dim_batch` 当初怎么建的），已完成，存档备查。

## 改东西的流程

Mac 改 → `git push` → Linux `cd /opt/cmc-rd-usp-dashboard && ./deploy.sh`。
**动到数据库表结构**（含放开某张表的约束）要先在 `~/code/cmc-schema-migrations` 写迁移，两端各跑一次 `./dbmig cmc_analytics upgrade head`，**先跑迁移再部署代码**。

## 关键提醒（别踩坑）

- **只读**：本项目绝不往 `cmc_rd` 写。唯一的写入点是 `cmc_analytics.manual.sample_result`（只追加，走单独账号 `usp_writer`）。要算/存分析结果放 `cmc_analytics`。
- **别用写账号**读数：只读走 `lims_reader`，不要用 ETL 的 `lucullus_etl` / `vicell_etl`。
- **数据量大**：单批次上百万点，画图前一定降采样（后端已做，前端别一次拉全量原始点）。
- **Mac 本地没有真数据**：只有空表结构 + 少量播种样本。看真数据开 SSH 隧道连 Linux（见 CLAUDE.md）。
- **通道显示名在数据库里**（`dim.channel_dict`），不要在前后端写死字典。

## 相关项目

- 工艺数据 ETL：`~/code/rd-lucullus-etl`；细胞 / 生化 ETL：`~/code/rd-vicell-etl`、`~/code/rd-nova-etl`
- 当天样品清单来源（批号注册系统）：`~/code/rd-batch-registry`
- 结构迁移（谁管数据库表结构）：`~/code/cmc-schema-migrations`（命令 `dbmig`）
- 统一门户：`~/code/cmab-hub`；统一认证：`~/code/cmab-mdm-platform`
- 架构白皮书：`~/code/CMAB_Data_Architecture_Whitepaper_V0_4.md`
- 同类看板（技术栈参照）：`~/code/cmc-rd-lims-dashboard`
