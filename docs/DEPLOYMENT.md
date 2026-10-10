# 部署与接入

> 版本：V0.6｜日期：2026-10-10｜状态：第一版及跨项目配套代码已在本地实现并验证；Mac Hub模拟预览已发布，真实Linux接入与验收未完成；未提交/push，Linux未部署。

本项目已有本地代码及模拟预览；Hub入口/代理、共享迁移、培训排除及源通知已按用户授权在各仓本地整合；生产数据库、服务账号及Linux服务尚未创建，生产Hub尚未发布这些改动。下列受管代码不是已执行或已获生产部署授权。第一版只读源系统；没有重跑/恢复/改源调度功能。

## 本地验证

README给出安装、模拟预览、测试和构建命令。API配置在backend/.env.example、collector在backend/.env.collector.example；真实模式必须配置MDM验签和已迁移的监控库，不能用占位值或内存降级。API绑定127.0.0.1:8025，前端固定5125，端口冲突报错。

模拟预览使用前端VITE_DEMO_MODE=true，不接后端或生产凭据，整页标模拟。生产构建必须未设置该变量；在真正发布时核对构建标识、提供文件和真实角色，不能把开发预览发布成真实运维状态。

## 本地配套代码与生产剩余工作

完整文件归属及链接见[integration导航](../integration/README.md)。旧审阅副本已移除，不重复安装drop-in或维护第二份迁移。

| 接入项 | 已完成的本地代码与验证 | 生产尚未完成 |
|---|---|---|
| Hub | cmab-hub/apps.ts仅SYS_ADMIN磁贴、hub-locations.conf的/ops/代理；角色规则、类型/构建、nginx -t通过 | 真实服务准备后协调发布磁贴；真实角色及直达验证 |
| 共享迁移 | cmc-schema-migrations追加20261010_ops_monitor_v1，接analytics_water_mart_perf_1009；唯一head、增量离线SQL、四表ORM对照通过 | 核对正式/培训当前revision，发布固定版本并在明确目标执行迁移 |
| 培训隔离 | rd-batch-registry/training_db_reset.sh排除ops_monitor数据，严格检查复制失败、换名/服务失败保护；隔离桩通过 | 原业务继续同步、schema及版本一致、运维四表为空的实际库对账 |
| 专用角色/ACL | integration/permissions.sql.example最低授权审阅材料 | 精确库/列与CONNECT/PUBLIC/继承核实，账号/凭据/ACL建立及允许/拒绝验证 |
| 原任务通知 | 7个源service和3个原cron顶层入口已接成功/失败；本项目deploy/linux/ops-notify-*及发送助手统一维护；桩验证保留退出码/原告警 | 观察服务安装、socket组/源身份连接、Linux成功/失败双路径送达及沙箱验证 |
| 运行托管 | deploy/linux/API、collector、静态前端受管配置；8025/5125仅本机 | 正式环境文件、OS身份/目录、Linux安装及同SHA验收 |
| cron计划摘要 | 原prometheus身份只读自己的crontab，仅导出三条固定任务计划；06:59准备摘要 | 安装schedule-export.service/timer，验证有效25小时及读取身份 |


API和collector分别使用opsmonitor-api/opsmonitor OS身份、不同数据库角色及环境文件；API无源数据库凭据或源文件权限。数据库最低授权参考材料还需核对CONNECT/PUBLIC/角色继承，不能把GRANT脚本代替实际权限证据。无pg_read_all_data、pg_read_server_files或通用sudo。

collector只需白名单单元元信息、生命周期journal记录、限定父日志、心跳/校验摘要、MDM产物stat以及运维表指定列。现有journald整组权限可能扩大读取范围：生产需受限导出或受控日志权限，不直接给API加入adm。若原日志含敏感业务数据，改用仅固定标记的受限输出；本轮实际生产ACL方案尚未验证。

cron摘要目录由prometheus拥有写权限，collector只有读取权限；文件不含命令/环境/秘密，最多64KiB、有效25小时，读不到或过期为未知。stock crontab读取可能需要其既有setgid，导出服务未启用NoNewPrivileges；ProtectSystem只读且代码只调用crontab -l，不给新源写权限。该沙箱仍需Linux实测。

Unix socket目录属于opsmonitor:opsmonitor-events，socket660；仅登记生产UID可发自己的任务。观察单元复用相应原User并只获socket连接权限；原ETL/备份不读取监控数据库。目录/组/环境文件的实际授权未执行。

## 通知与兜底

OnSuccess/OnFailure观察单元在源单元已经结束后发送提示，不使用ExecStopPost把还未完整终止的单元当完成。源仓service中新增指令不重置已有OnFailure告警。目标Linux只读确认systemd255支持该机制，观察服务尚未生产验收。cron已在原顶层入口整合EXIT trap并保留原退出码；SIGKILL/主机失联不能保证发送。

监控先具备队列和白名单，再接源通知。通知失败只留下本机提示，发送助手最终exit0；源程序失败仍保留自己的退出码。每日07:00、启动补采、管理员更新均只读运维证据，不重跑源任务。内部等待事件不持续扫描任务或刷新网页。

## 发布与回滚

仍按Mac验证→各仓提交/push→Linux固定完整SHA→所属部署流程→验收；本轮未提交/push。共享对象只经cmc-schema-migrations；培训排除代码已完成，持久化发布必须协调更新实际执行的training仓版本，并验证隔离。发布前复核8025/5125、已有dirty状态、迁移revision、权限和服务读取范围，不能手工拷代码形成独立版本。

保留旧构建/配置和各仓版本；源通知可撤去而保留原任务行为。监控停机不影响源任务，恢复后队列补查并标历史缺口。数据库回滚保留监控/审计历史，不默认DROP；共享迁移的downgrade明确拒绝破坏性删除。健康200、构建成功或合成JWT测试都不能代替真实任务/角色验收。


## 协调发布顺序（2026-10-10已授权，执行事实见发布记录）

1. 固定各仓完整SHA及新revision；核对两库版本、端口和dirty状态，安排源/监控独立回退。
2. 将已验证的培训排除脚本发布到实际cron调用的 `/opt/rd-batch-registry-training`，保持原00:00计划；验证新库失败不切换。不能只更新正式批号仓而漏掉培训执行副本。
3. 按共享迁移流程备份并应用明确revision、配置监控自有角色及源只读身份/受限日志读取；无自动建表或宽泛日志权限降级。
4. 安装API/collector、正式非模拟前端以及06:59计划摘要托管，验证07:00和启动补查；先具备队列/socket，后接通知。
5. 观察服务由monitor仓统一提供：将7个 `deploy/linux/ops-notify-*.service` 安装到systemd目录但不enable/start（只被原单元触发）；配置opsmonitor-events连接范围。再按各源仓原部署入口更新service/脚本，仅daemon-reload不启动ETL/备份。源原Unit中的OnFailure通知与旧告警并列，不复制已删除的审阅drop-in。
6. 验证消息提示与重新核对源结果、原告警/退出码和最小读取范围后，协调发布Hub入口/路由；真实管理员/非管理员浏览器及直接API验收另行记录。

2026-10-10用户已建立GitHub仓库并授权顺序发布，执行以 [协调发布记录](RELEASE_20261010.md) 为准，覆盖已确认迁移、读取身份和服务托管；原任务仍不主动执行。`scripts/deploy_linux.py` 按prepare/migrate/configure/start/sources/hub分阶段执行，每阶段要求明确本项目完整SHA。source阶段从所属仓service提取通知指令生成受管drop-in，保留原已安装的业务配置和告警；不启动源单元、不改变原timer。新增受限journal socket导出服务的生产配置必须设置OPS_JOURNAL_SOCKET_PATH，collector不得加入宽泛journal组。

本地验证不替代真实迁移、培训数据对账、Linux UID/ACL/沙箱和认证浏览器验收。任何通知失败只能让监控补查/未知，不得改变源任务状态或自动重跑。


## Mac本地预览发布

已获用户授权，更新在用Hub的frontend/dist，检查当前nginx配置后使新增/ops路由生效；不改变监听地址或其他系统配置。监控使用VITE_DEMO_MODE=true构建到frontend/dist，以deploy/mac/com.qingcheng.cmc-platform-monitor.frontend.plist托管Vite preview，固定127.0.0.1:5125，端口冲突报错。前端每页保留模拟标识，不调用真实后端或读取生产凭据。此Mac预览不可作为Linux正式构建发布。

安装前保留原Hub产物、monitor产物及已有plist备份，仅替换已核实属于本项目的5125开发进程。安装位置~/Library/LaunchAgents，日志~/Library/Logs/cmc-platform-monitor；正式监听、身份/数据接入与模拟预览状态分别验收。这里不安装Linux通知单元、创建数据库对象或启动真实采集器。

### 2026-10-10 实际发布结果

已执行 `bash scripts/deploy_mac_preview.sh --apply`，退出0。Hub与模拟前端TypeScript/Vite构建通过；真实nginx配置 `nginx -t` 通过并平滑reload，仅更新路由，监听地址保持。LaunchAgent `com.qingcheng.cmc-platform-monitor.frontend` 实测running、PID46587，127.0.0.1:5125监听；安装plist与仓内模板逐字节一致，RunAtLoad/KeepAlive生效。该Agent在用户登录会话自动运行，不是关机后仍在线的服务。

通过5100访问 `/ops/` 与详情 `/ops/tasks/ingest-night` 返回200；Hub在用JS `index-DT37-Kxg.js`、monitor在用JS `index-Crb48fRu.js` 与刚构建文件逐字节一致。公开 `/ops/api/v1/health` 返回404；8025真实API未启动。浏览器从Hub路径实际打开模拟卡片、进入详情/历史并返回；更新按钮可操作，合成结果保持模拟范围。截图 [Mac Hub模拟预览](mac-hub-preview.png)。浏览器当前未登录，真实SYS_ADMIN磁贴点击与非管理员浏览器验收未执行；纯角色规则检查通过不替代真实登录。

发布备份位于 `.local/mac-preview-20261010-130644`（Git忽略），包含原Hub/monitor构建及发布前磁盘路由文件；当时磁盘路由已含ops，不是旧nginx已加载配置的完整快照。需要撤回时先bootout本项目Agent，可用备份恢复原Hub构建；路由撤回须单独审查ops段并nginx -t后reload，保留其他应用。未运行撤回。

未提交/push、未部署Linux、未安装源通知单元，未运行源任务/迁移或创建数据库/权限；07:00及结束触发真实采集仍待生产接入。

### 2026-10-10 D14显示调整已更新Mac预览

在已有LaunchAgent托管服务下重建模拟frontend/dist，固定5125直接提供新产物，不需重启nginx或改变Hub磁贴。新JS为 `index-BRamCZfm.js`，CSS `index-C1DiSWi4.css`，实际服务JS与本次构建逐字节一致。真实浏览器通过5100验证主区和折叠分区；用户5125页已刷新。先前构建和发布记录保留为历史，最新版按本节识别；仍是模拟数据，不执行Biacore接管或源任务。
