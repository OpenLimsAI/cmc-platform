# 数据中台运维看板 — cmc-platform-monitor

> 版本：V0.8｜日期：2026-10-11｜状态：Linux真实监控、Hub入口及MDM逐份恢复验证已发布；已有真实备份恢复及权限核验通过。下一次自然每日备份完整链路、真实MDM角色浏览器登录待验收。Mac保留模拟预览。

目标：独立监控Linux数据中台ETL与自动备份，Hub入口和后端业务访问仅MDM SYS_ADMIN，第一屏异常优先，V1只读。已确认目标不重复询问；全部覆盖仍是目标。

## 当前状态

2026-10-09已只读盘点172.19.0.105所列范围：10个在用顶层组，7个自定义timer及5条业务cron，另登记停用/历史入口、5个外部或历史备份源及覆盖缺口。没有发现同ETL的cron+timer重复入口；不能据此声明全平台100%覆盖。任务证据和调查限制见盘点。

已完成本项目前后端代码：四列圆角浅色卡片、异常优先、任务详情与历史/脱敏证据、MDM SYS_ADMIN 后端守卫、固定清单只读采集、持久化事件队列、结束通知接收、每日07:00兜底与按需更新。绿色/红色/黄色/灰色四种状态，不设置浅蓝或独立运行卡片。

生产存储为 cmc_analytics.ops_monitor，代码不会在启动时建表；缺MDM验签/存储配置拒绝启动。任务观测90天、访问记录180天。模拟预览明确标注，不读取生产数据。Hub注册/路由、共享迁移、培训复制排除及源通知已在各项目本地代码整合；Linux已完成正式/培训共享迁移、专用列读取角色、受限journal导出、托管和通知安装；已读取10个在用任务真实证据。真实角色浏览器及自然结束通知另行验收。外部5个来源显示未接入，停用任务保留。

固定端口8025/5125，Linux均仅监听127.0.0.1，经 [Linux Hub /ops](http://172.19.0.105:5100/ops/) 访问真实监控；未登录跳到MDM统一登录，仅SYS_ADMIN可读业务API。Mac Hub [5100/ops](http://localhost:5100/ops/) 继续是明确标注的模拟预览，5125由LaunchAgent托管、Mac 8025未启动。各仓已提交/push、Linux拉取同一指定SHA。2026-10-10初次发布未改源调度、未主动执行源ETL、业务备份、恢复或培训复制；该次迁移前执行了保护性分析库备份。2026-10-11按P16授权对已有MDM备份执行独立容器恢复验证。用户已授权其他项目本地配套代码修改，整合归属见[integration导航](integration/README.md)；父PORTS登记保持8025/5125。

## 本地启动与验证

只看界面（模拟数据，不需要生产凭据）：

```sh
cd /Users/qingcheng/code/cmc-platform-monitor
npm --prefix frontend ci
npm --prefix frontend run dev:demo
```

已托管的预览请打开 [Mac Hub看板](http://localhost:5100/ops/)；[Hub登录](http://localhost:5100/)后SYS_ADMIN账号按规则可见入口。无需再运行开发服务器；5125已被托管服务占用，不能同时运行dev。上面的dev命令仅用于停止托管后的开发。模拟页面可直接访问，仅展示合成数据，不代表已完成真实MDM会话验收。真实前端使用 `npm --prefix frontend run dev`，需要Hub/MDM同源接入；不能用演示登录读取真实来源。

后端安装与测试（测试使用隔离内存存储与合成数据）：

```sh
cd /Users/qingcheng/code/cmc-platform-monitor/backend
uv sync --locked
uv run pytest -q
```

配套离线验证：`python3 scripts/check_companion_integration.py`（所有源任务/数据库/服务均为桩）、`backend/.venv/bin/python scripts/check_monitor_schema.py`、`node scripts/check_hub_integration.cjs`（需Hub已有开发依赖）。

前端验证：`npm --prefix frontend test`、`npm --prefix frontend run build`。已通过的项目、浏览器检查及未验证部分见 TEST_ACCEPTANCE。

真实API的启动命令为 `uv run uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8025`；配置入口 backend/.env.example。它要求已完成迁移的监控库与MDM验签配置，不能直接用示例占位值运行。Linux采集进程为 `python -m app.collector`，现已由systemd托管；任务结束提示、启动补采及每日07:00兜底均已配置。生产执行事实、版本及剩余验收见 [协调发布记录](docs/RELEASE_20261010.md) 与 DEPLOYMENT。

## MDM逐份恢复验证（P16）

用户已确认两仓实现、测试及Linux发布。MDM负责独立Docker恢复/同备份snapshot基线检查，monitor只读展示验证范围与结果；不使用Mac现有真实库，不在原生正式PG建临时恢复库。已有真实备份已在Linux独立容器恢复通过并清理，报告已进入看板。详见[本次验证发布记录](docs/RELEASE_20261011_BACKUP_VERIFY.md)，下一次自然每日链路仍待验收，不用旧验证给新备份标绿。

## 在用文档与权威分工

| 文件 | 权威主题 |
|---|---|
| [AGENTS](AGENTS.md) | 长期工作约定、必读入口，不承载单次授权 |
| [USER_REQUIREMENTS](docs/USER_REQUIREMENTS.md) | 目标、范围与UR01–UR08业务验收；沿用已有文件名 |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | 边界、依赖、采集、存储、培训复制影响、最小权限与审计架构 |
| [TASK_INVENTORY](docs/TASK_INVENTORY.md) | 任务/父子关系、源证据、实际计划、调查范围和缺口 |
| [MONITORING_RULES](docs/MONITORING_RULES.md) | 状态算法、汇总与逐任务阈值草案 |
| [DATA_MODEL](docs/DATA_MODEL.md) | 实际源字段/时间语义与拟建逻辑模型 |
| [API_SPEC](docs/API_SPEC.md) | 接口、MDM鉴权/会话与读取限制 |
| [INFORMATION_ARCHITECTURE](docs/INFORMATION_ARCHITECTURE.md) | 页面与交互 |
| [TEST_ACCEPTANCE](docs/TEST_ACCEPTANCE.md) | 验证场景、证据与分阶段验收 |
| [DEPLOYMENT](docs/DEPLOYMENT.md) | 发布前提、多仓版本和回滚 |
| [RELEASE_20261010](docs/RELEASE_20261010.md) | 首次实际多仓SHA、迁移、备份、权限与上线验收 |
| [RELEASE_20261011_BACKUP_VERIFY](docs/RELEASE_20261011_BACKUP_VERIFY.md) | MDM自动恢复验证两仓版本、隔离测试、真实恢复与剩余验收 |
| [ADMISSION_CHECKLIST](docs/ADMISSION_CHECKLIST.md) | 白皮书Part V C01–C15逐项结论 |
| [DECISIONS](docs/DECISIONS.md) | 已确认目标、D01–D15已确认基线、发布授权与待验收项 |
| [CHANGELOG](docs/CHANGELOG.md) | 改动、原因、影响、实际验证及提交/部署状态 |
| [HANDOFF](docs/HANDOFF.md) | 状态导航，仅引用权威文件，不产生后续授权 |

首页主区展示Linux在用任务；外部备份与已停用任务分别默认收起，关注数只统计主区。Biacore工作站至NAS现状及未来集中管理方向见D14。

沿用已有专题，不新增同名或重复主题文档。原始文档保存在[V0.1历史基线](docs/archive/V0_1_BASELINE.md)，仅供溯源，不作现行指令。本地启动方式见上文；生产接入按DEPLOYMENT逐项完成后发布。
