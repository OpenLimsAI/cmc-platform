# 两页看板 GitHub → Linux 发布记录

> 版本：0.1｜日期：2026-10-09｜状态：业务代码已推送并部署，Linux隔离测试、Hub资源和只读统计核验通过；真实登录后的页面、两档身份及下载待验收。

## 范围与版本

用户明确要求“github，然后Linux同步更新”。按[两页整理设计](../changes/20261009-two-page-dashboard.md)发布：仅总览、取样点趋势；总览WFI/PW/PS三卡片各显示点位数和当前自然年样品总数；撤销三个独立功能/API，趋势原文、来源和导出保留。位置及系统归属仍等待用户对照表。

- 仓库：`git@github.com:qingcheng81/cmc-water-system-dashboard.git`，分支main。
- 发布前Mac/GitHub/Linux基线：`b77213f3cc1ebb17b71cc9a3bc74580573887284`，工作区干净。
- 本轮业务提交：`3395586fd44d86baa08cdcb366bd5a88a1043a44`。Mac提交、GitHub push、Linux `git pull --ff-only origin main`后，按完整SHA执行现有deploy.sh；构建、重启及检查完成。
- 主机prometheus，SSH用户prometheus、端口13568；检出`/opt/cmc-water-system-dashboard`，APP_ENV=linux。
- 未修改依赖项目；本轮只读核对其Linux检出均干净：Hub `827201d159da65479801cf119483e49b837ec606`，MDM `47e1405ffc0387885ad1ebeae5e40a72b17628f8`，QC ETL `687ad67d76169db273f30050fc2c439bc8151c22`，迁移仓库 `6aaf682f2aa560cdc2c20292bb722ba2d233ff29`。这些是Git检出版本，不替代各依赖服务自身的完整运行验收。

发布执行与以下服务/数据核查在2026-10-09约15:40–15:45（Asia/Shanghai）完成；随后文档提交仍按GitHub→Linux同步。文档跟进提交不修改backend、frontend或发布脚本，业务构建对应上列完整SHA；最终检出HEAD以Git为准。

## 备份、配置与发布故障处理

发布前保护备份位于`logs/two-page-predeploy-20261009-154006/`，包含旧SHA、旧前端dist、原backend/.env和服务/nginx配置；目录0700、环境配置0600。成功部署脚本的配置备份为`logs/deploy-20261009-154351/`。路径均相对Linux项目目录。

首次执行构建通过、后端健康200，但静态入口403。已核实原因：备份阶段umask 077继承到构建，使index.html为0600、assets目录为0700；nginx日志明确Permission denied。这是此次发布命令的权限设置问题。恢复umask 022后重新运行同一业务SHA的deploy.sh，index.html为0644、assets为0755，入口恢复200，脚本成功结束。未扩大敏感配置权限；backend/.env仍0600，并与发布前备份逐字一致。运维文档已补充备份与构建权限要求。

无数据库结构变化，未执行迁移、ETL、数据导入/修正、角色授权或会话策略变更；未从Mac复制业务数据或凭据。可按原固定SHA重建、恢复备份配置并复核服务/Hub资源；无业务数据回滚步骤。

## 实际验证

| 检查 | 实际结果 | 证据边界 |
|---|---|---|
| Mac隔离测试 | 后端49项、前端9项通过；TypeScript/Vite构建通过 | 详见两页变更记录 |
| Linux隔离测试 | `.venv/bin/python -m pytest -q`：49通过，3.41秒；`pnpm --dir frontend test`：9通过，约195毫秒 | 合成身份/数据与内存临时表，不写真实业务库 |
| Linux构建 | 锁文件安装及TypeScript/Vite构建通过，Vite约9.74秒 | JS约2.14MB仍有大包警告；后端有Starlette/httpx弃用警告 |
| 服务与端口 | water-backend active；8015、5115只监听127.0.0.1；后端及Hub代理health均200 | 健康接口不代表完整业务验收 |
| 运行接口 | OpenAPI八条路由，与docs/07一致；总览/比较组/上下文/筛选/趋势/追溯匿名401 | 未伪造真实MDM身份调用业务接口 |
| 删除接口 | results、summaries、data-quality均404，trace子路径仍存在 | 趋势来源功能继续保留 |
| Hub资源及深链 | /water/、overview、trends、三个旧路径均返回200及同一SPA入口；JS/CSS均200，下载字节与dist文件完全一致 | 旧路径转总览及提示由前端执行，真实浏览器交互仍待登录验证 |
| 真实数据 | Linux cmc_analytics／lims_reader，只读预检通过，transaction_read_only=on；三卡片与独立CTE去重SQL一致 | 仅看板入选范围，不代表完整正式样品/点位台账 |

资源SHA256：

| 文件 | SHA256 |
|---|---|
| index.html | `ad3efc0050d56f55adb96652153347fa085acf14fd84833ffba4000c9b8333be` |
| assets/index-DV0qctOd.js | `bea04d14ed56ebf23209b3994a507b53c16ee99ae0769e7d3711810bb8cc6f43` |
| assets/index-u-HZcgS5.css | `9a4d15c2c137208529f20787b8c741b41f7bbfe1c281194c57b8286188d1f21c` |

## Linux三卡片只读对账

年度范围为[2026-01-01上海零点,2026-10-10上海零点)，截至10月9日。点位数不限年度；固定QC来源、Sample、三类水、两条入选规则及Reviewed/Completed状态。独立SQL先分别去重点位/样品，再计数，不直接复用业务聚合表达式。

| 标签 | 点位数 | 年度样品总数 |
|---|---:|---:|
| WFI | 74 | 1424 |
| PW | 219 | 1710 |
| PS | 60 | 37 |

Linux STAGING_DATA_ORIGIN=oracle_etl；source_cutoff/context_id仍为空，未核验QC作业新鲜度。Mac此前观察为WFI 74/1416、PW 219/1710、PS 60/36；两环境各自独立对账通过，数据数量不同不能由代码发布或拷贝数据来消除，也不能据此确认哪一环境具备最新完整来源。

## 后续验收

服务与资源部署完成；真实登录后的三卡片显示、旧路径提示、趋势操作、Viewer/Exporter身份、三类下载落盘及退出/多标签尚待验收。无已登录会话，未把匿名HTTP与隔离测试写为这些用例通过。其余数据治理、性能与代码差距继续保留在[docs/10](../10-decisions-open-items.md)，[STATUS](../STATUS.md)为汇总。
