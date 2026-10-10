# 数据中台运维看板 — cmc-platform-monitor

> 版本：V0.6｜日期：2026-10-10｜状态：第一版及跨项目配套代码已在本地实现并验证；Mac Hub模拟预览已发布，真实Linux接入与验收未完成；未提交/push，Linux未部署。

目标：独立监控Linux数据中台ETL与自动备份，Hub入口和后端业务访问仅MDM SYS_ADMIN，第一屏异常优先，V1只读。已确认目标不重复询问；全部覆盖仍是目标。

## 当前状态

2026-10-09已只读盘点172.19.0.105所列范围：10个在用顶层组，7个自定义timer及5条业务cron，另登记停用/历史入口、5个外部或历史备份源及覆盖缺口。没有发现同ETL的cron+timer重复入口；不能据此声明全平台100%覆盖。任务证据和调查限制见盘点。

已完成本项目前后端代码：四列圆角浅色卡片、异常优先、任务详情与历史/脱敏证据、MDM SYS_ADMIN 后端守卫、固定清单只读采集、持久化事件队列、结束通知接收、每日07:00兜底与按需更新。绿色/红色/黄色/灰色四种状态，不设置浅蓝或独立运行卡片。

生产存储为 cmc_analytics.ops_monitor，代码不会在启动时建表；缺MDM验签/存储配置拒绝启动。任务观测90天、访问记录180天。模拟预览明确标注，不读取生产数据。Hub注册/路由、共享迁移、培训复制排除及源通知已在各项目本地代码整合；完整运行仍需执行迁移、配置专用只读账号/受限日志权限并安装托管与观察服务。代码完成不能等同已上线。外部5个来源显示未接入，停用任务保留。

固定端口8025/5125；Mac Hub [5100/ops](http://localhost:5100/ops/) 已发布模拟预览，5125由LaunchAgent自动托管，8025后端未启动；Linux未部署，无真实角色浏览器验收；未创建数据库对象或权限，未改原调度，未运行ETL/备份/恢复/迁移，未提交/push。用户已授权其他项目本地配套代码修改，整合归属见[integration导航](integration/README.md)；父PORTS登记保持8025/5125。

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

真实API的启动命令为 `uv run uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8025`；配置入口 backend/.env.example。它要求已完成迁移的监控库与MDM验签配置，不能直接用示例占位值运行。Linux采集进程为 `python -m app.collector`，需配套权限及源接入；本轮未启动真实采集。生产部署模板和配套材料见 DEPLOYMENT；当前仅Mac模拟预览发布完成。

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
| [ADMISSION_CHECKLIST](docs/ADMISSION_CHECKLIST.md) | 白皮书Part V C01–C15逐项结论 |
| [DECISIONS](docs/DECISIONS.md) | 已确认目标、D01–D14已确认基线与生产待接入项 |
| [CHANGELOG](docs/CHANGELOG.md) | 改动、原因、影响、实际验证及提交/部署状态 |
| [HANDOFF](docs/HANDOFF.md) | 状态导航，仅引用权威文件，不产生后续授权 |

首页主区展示Linux在用任务；外部备份与已停用任务分别默认收起，关注数只统计主区。Biacore工作站至NAS现状及未来集中管理方向见D14。

沿用已有专题，不新增同名或重复主题文档。原始文档保存在[V0.1历史基线](docs/archive/V0_1_BASELINE.md)，仅供溯源，不作现行指令。本地启动方式见上文；生产接入按DEPLOYMENT逐项完成后发布。
