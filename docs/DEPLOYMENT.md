# 部署与接入

> 版本：V0.7｜日期：2026-10-10｜状态：已提交/push并部署Linux真实监控及Hub入口；服务、采集、权限和培训空表核验通过。真实MDM角色浏览器及下一次自然任务端到端通知待验收；详见 RELEASE_20261010。Mac保留模拟预览。

第一版只读源运维证据，无重跑、恢复、修改调度或任意文件读取功能。2026-10-10用户D15授权发布已执行；原监控部署事实、完整多仓SHA及备份证据在 [RELEASE_20261010](RELEASE_20261010.md) 维护；新增MDM逐份验证的两仓版本、资源实测和未验收项见 [RELEASE_20261011_BACKUP_VERIFY](RELEASE_20261011_BACKUP_VERIFY.md)。下方Mac记录为当时历史，不覆盖Linux最新状态。

## 当前Linux配置

- 项目 `/opt/cmc-platform-monitor`，GitHub独立仓库；后端API127.0.0.1:8025、nginx正式静态前端127.0.0.1:5125，经Hub5100的 `/ops/` 同源访问，未增加ufw直连端口。
- API/collector/evidence及schedule-export.timer已active+enabled；配置在root600的 `/etc/cmc-platform-monitor/{api,collector}.env`，密钥与连接串不进Git。API仅自有监控角色，collector写自有四表、源reader精确运维列只读；来源工作进程不继承API密钥或自有writer连接。
- journal证据服务固定7个单元、真实peer、32天上限及有界游标页；collector只获socket连接，不加adm/systemd-journal，不获通用sudo。固定7个源service元信息可读。
- 原prometheus身份06:59只读导出3组cron计划摘要，collector每日07:00兜底、启动补采、任务结束事件及管理员按需更新。内部等待队列不持续扫描任务或刷新网页。
- 10组任务通知已发布：7个systemd受管drop-in追加OnSuccess/OnFailure，3个原cron顶层EXIT trap。原User/ExecStart、既有告警及timer时刻保持；观察服务仅被结束触发，不enable/start源任务。成功/失败配置与真实producer peer已核验，下一次自然源任务完整链路仍待观察。
- 正式/培训分析库均为20261010_ops_monitor_v1；实际training调用副本使用专项发布分支，仅带入本次脚本，避免升级其他应用。当前培训四表空；下一次00:00自然同步后复核结构、迁移版本、原业务和四表空，不能为验收主动执行培训复制。
- Linux前端构建不含VITE_DEMO_MODE；Mac始终保留标注模拟的构建，不能把Mac dist复制到Linux。

## 固定版本发布步骤

### 2026-11-04总仓库内开发、独立目录发布

本地权威工作副本已迁入`OpenLimsAI/cmc-platform`的`cmc-platform-monitor/`；Linux本次实查仍为原独立Git仓库和既有`/opt/cmc-platform-monitor`路径。本次保留运行路径、origin及服务配置：先将本项目显式文件清单提交/push至总仓库，再以该提交的监控子目录完整Git tree、Linux当前提交为父，建立`codex/monitor-upstream-release-20261104`发布分支并push至同一总仓库。Linux从该分支fetch并快进到核实的完整发布SHA，再运行现有monitor专项发布脚本。

这是本次明确授权的定向发布，不建立向旧仓库的自动同步、不发布其他子项目、不切换整体运行目录。发布提交与总仓库提交因目录布局不同而SHA不同，必须核对`总仓库提交:cmc-platform-monitor`与`发布提交^{tree}`相等，记录两者完整SHA；Linux HEAD须与GitHub发布分支完全相同。回退使用本次发布前Linux SHA和原构建，保留监控历史。下方旧独立仓库/多仓流程保留其原适用阶段。

执行前复查目标主机、dirty工作区、端口、依赖版本及迁移revision；不覆盖未提交文件。所有代码按Mac验证→对应GitHub提交/push→Linux相同完整SHA，禁止手工复制或直接改服务器业务代码。培训专用分支与正式批号仓分别记录，不擅自改为pull main。

本项目 `scripts/deploy_linux.py <phase> <完整SHA>` 在服务器通过已授权sudo按阶段执行，校验本项目HEAD；版本锁见deploy/linux/release-20261010.json。现有阶段不是每次更新都重复运行，后续按变化选择必要阶段：

1. prepare：环境/身份目录、锁定依赖及正式前端构建，先发布实际training副本及迁移仓版本。
2. migrate：核对两库revision，保护性备份、目录清单检查与SHA后，在所属共享链执行 `./dbmig <库> upgrade 20261010_ops_monitor_v1`，核对current。没有升级时不重复迁移。
3. configure：精确列授权与分离环境；只配置本次专用角色，不扩大既有业务权限。
4. start：安装/启动监控及只读计划摘要服务，不启动源任务。实际来源读取并核验队列、沙箱与权限。
5. sources：拉取已确认的各仓SHA，安装观察服务与受管通知drop-in；仅daemon-reload，比较原User/ExecStart保持一致。
6. hub：构建Hub，保留旧dist，nginx -t并平滑reload；最后核对实际提供的JS与磁盘产物逐字节一致、真实API转发及角色拒绝。

迁移只改自有ops_monitor四表与索引，不自动建库，不改源raw/meta结构。监控进程不在启动时建表。权限示例仅审阅，当前实际脚本/授权与拒绝证据见发布记录。

## 验证与回退

### D18前端单独更新（2026-10-14已授权）

本次两次页面调整仅涉及前端及文档。复用此前历史记录入口修正的前端发布路径：Mac验证并显式文件清单commit/push；Linux检查干净main、git pull --ff-only并核对完整SHA，保留原frontend/dist到Git忽略的.local目录，再以prometheus执行 `env -u VITE_DEMO_MODE npm --prefix frontend run build`。既有nginx直接提供dist，不重启API/collector/nginx，不重复依赖安装、数据库迁移、权限或源通知配置。发布后核对三端SHA、Hub实际HTML/JS/CSS与磁盘及Mac正式构建、服务/监听和只读API守卫；Mac在用dist仍为模拟构建，不能要求与Linux正式JS逐字节相同。

需要回退时回到发布前已确认SHA并重建正式前端；原dist备份用于恢复对应静态产物，保留监控历史和原任务调度。本次实际SHA、产物及检查结果在TEST_ACCEPTANCE D18发布验收维护。

本地测试见README及TEST_ACCEPTANCE；服务器 `verify_linux_release.py permissions/api/notifications` 以实际角色/peer检查。api探针使用本机MDM验签配置构造短期合成角色令牌，sub=0、username=release-verification，只证明接口守卫，不能代替真实MDM登录。通知探针只请求重新读证据，不伪造成功、失败或启动源单元。

保留目录 `/var/backups/cmc-platform-monitor/20261010`，包含迁移前两库dump/SHA、旧Hub dist及已有受管文件。回退先停本项目API/collector/证据/摘要托管、撤回本项目源通知drop-in（保留旧告警及原timer），Hub恢复旧构建/路由后nginx -t/reload；源码退到明确已发布版本。源通知不可用不会改变原程序退出码。禁止默认DROP自有四表：保留运维/审计历史，迁移downgrade拒绝破坏性删除。任何整库恢复须另行评估并授权，本次未执行回退或恢复。

健康200和构建成功不足以验收。现已验证真实读取、持久化历史、最小权限、Hub API代理及服务；尚待真实管理员/非管理员浏览器、下一次自然成功/失败通知、07:00兜底、00:00培训隔离、长期保留及中断恢复。外部5源与恢复证据缺口继续明确显示。

## Mac本地预览发布

已获用户授权，更新在用Hub的frontend/dist，检查当前nginx配置后使新增/ops路由生效；不改变监听地址或其他系统配置。监控使用VITE_DEMO_MODE=true构建到frontend/dist，以deploy/mac/com.qingcheng.cmc-platform-monitor.frontend.plist托管Vite preview，固定127.0.0.1:5125，端口冲突报错。前端每页保留模拟标识，不调用真实后端或读取生产凭据。此Mac预览不可作为Linux正式构建发布。

安装前保留原Hub产物、monitor产物及已有plist备份，仅替换已核实属于本项目的5125开发进程。安装位置~/Library/LaunchAgents，日志~/Library/Logs/cmc-platform-monitor；正式监听、身份/数据接入与模拟预览状态分别验收。这里不安装Linux通知单元、创建数据库对象或启动真实采集器。

### 2026-10-10 实际发布结果

已执行 `bash scripts/deploy_mac_preview.sh --apply`，退出0。Hub与模拟前端TypeScript/Vite构建通过；真实nginx配置 `nginx -t` 通过并平滑reload，仅更新路由，监听地址保持。LaunchAgent `com.qingcheng.cmc-platform-monitor.frontend` 实测running、PID46587，127.0.0.1:5125监听；安装plist与仓内模板逐字节一致，RunAtLoad/KeepAlive生效。该Agent在用户登录会话自动运行，不是关机后仍在线的服务。

通过5100访问 `/ops/` 与详情 `/ops/tasks/ingest-night` 返回200；Hub在用JS `index-DT37-Kxg.js`、monitor在用JS `index-Crb48fRu.js` 与刚构建文件逐字节一致。公开 `/ops/api/v1/health` 返回404；8025真实API未启动。浏览器从Hub路径实际打开模拟卡片、进入详情/历史并返回；更新按钮可操作，合成结果保持模拟范围。截图 [Mac Hub模拟预览](mac-hub-preview.png)。浏览器当前未登录，真实SYS_ADMIN磁贴点击与非管理员浏览器验收未执行；纯角色规则检查通过不替代真实登录。

发布备份位于 `.local/mac-preview-20261010-130644`（Git忽略），包含原Hub/monitor构建及发布前磁盘路由文件；当时磁盘路由已含ops，不是旧nginx已加载配置的完整快照。需要撤回时先bootout本项目Agent，可用备份恢复原Hub构建；路由撤回须单独审查ops段并nginx -t后reload，保留其他应用。未运行撤回。

该次Mac预览发布当时未提交/push或部署Linux；后续D15发布状态见本文首节及RELEASE_20261010。

### 2026-10-10 D14显示调整已更新Mac预览

在已有LaunchAgent托管服务下重建模拟frontend/dist，固定5125直接提供新产物，不需重启nginx或改变Hub磁贴。新JS为 `index-BRamCZfm.js`，CSS `index-C1DiSWi4.css`，实际服务JS与本次构建逐字节一致。真实浏览器通过5100验证主区和折叠分区；用户5125页已刷新。先前构建和发布记录保留为历史，最新版按本节识别；仍是模拟数据，不执行Biacore接管或源任务。


## P16专项更新与回滚

MDM先按既有deploy/deploy.sh固定SHA流程发布，再运行deploy/linux/install_backup_verification.py，配置固定镜像摘要及隔离service/path；原02:00 timer不改。monitor按scripts/deploy_backup_verification_monitor.py --sha <完整SHA>发布仅本项目构建/API/collector，不重复共享迁移、源通知或其他仓库发布。最后检查源/验证独立结果、摘要读取与私有资源拒绝、实际Hub构建及无容器残留。回滚先停用MDM verify.path并移除60-backup-verification.conf，保留备份timer/文件；monitor可回退前一代码SHA，四表无downgrade。详情只在本次发布记录维护。


## D17按设备归档专项发布

本次只发布monitor仓库代码与配置：Mac验证并commit/push，Linux干净工作区拉取同一完整SHA，复用 `scripts/deploy_backup_verification_monitor.py --sha <完整SHA>` 进行生产前端构建及API/collector重启。该脚本虽然沿用P16名称，仅执行本项目构建/托管；不重复迁移、权限、源通知安装或MDM/ingest发布。启动补采仅只读核对已有证据。旧ingest-day/night结束通知仍按原身份接受，新设备结果在collector内派生。回退到此前monitor已发布SHA并重建/重启，保留原历史；不删除JSONB字段或数据库记录。实际发布结果仅在TEST_ACCEPTANCE维护。
