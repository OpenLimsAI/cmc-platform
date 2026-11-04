# API 与鉴权契约

> 版本：V0.7｜日期：2026-10-10｜状态：已提交/push并部署Linux真实监控及Hub入口；服务、采集、权限和培训空表核验通过。真实MDM角色浏览器及下一次自然任务端到端通知待验收；详见 RELEASE_20261010。Mac保留模拟预览。

实际浏览器前缀`/ops/api/v1`，Hub剥`/ops`转后端`/api/v1`，本地代码已落实该前缀；Linux真实API和Hub /ops代理已发布，Mac保留模拟预览；真实角色浏览器尚待验收。

## 接口与读取限制

| 方法 | 后端路径 | 用途 |
|---|---|---|
| GET | /api/v1/health | 建议仅本机探针，最小存活，不经Hub公开，不含任务/数据库/配置 |
| GET | /api/v1/overview | 顶层与子任务计数、异常、采集时间与缺口 |
| GET | /api/v1/tasks | 分类型/状态/关键词分页 |
| GET | /api/v1/tasks/{task_key} | 计划、最新观测、关系和证据摘要 |
| GET | /api/v1/tasks/{task_key}/runs | 有界历史及来源关联，分页 |
| GET | /api/v1/tasks/{task_key}/evidence | 指定证据ID的白名单脱敏片段，不返回任意文件 |

实现页≤100条、历史默认7天/单请求≤31天；只展示白名单标记及有界脱敏摘要；源查询每次≤500条、超时预算见MONITORING_RULES。读取范围和访问留痕已确认，上限已作为本地实现参数；源读取截断时必须返回has_more/truncated/range，不能把前500条说成全部。API默认从缓存/自有历史读取；证据只取已脱敏材料。事件触发方案保留管理员按需更新运维观测：接口契约随D09确认后补齐，仅请求固定只读采集器并合并并发，不执行源任务、任意shell或重型查询。

## 本机结束通知与人工更新（接入草案）

源任务结束通知使用ARCHITECTURE所述本机IPC/事件队列，不作为浏览器业务API；不开放匿名event接口、不要求源程序取得管理员MDM token。接收端按本机进程身份与固定任务范围限制权限，不采信通知中的成功结论。

人工“更新状态”的契约已在本项目实现，仅SYS_ADMIN可用；合并并发、异步采集并返回更新请求引用。只刷新运维观测，不接受命令或源任务重跑参数。overview/detail仍读取快照，更新失败显式显示当前未知和历史截至时间。

## MDM身份及统一会话

全部业务接口验证MDM access JWT：固定允许算法与对应密钥（不信token自选算法）、签名、exp、type=access、有效sub，以及MDM实际契约中提供的其他必要claims。配置缺失拒绝启动，配置按目标环境核实；不提供开放模式。

角色必须含SYS_ADMIN，must_change_password必须完成后才可进入。无token/无效/过期/错误类型401；无SYS_ADMIN或临时密码403；不能按admin用户名放行，DEPT_ADMIN不自动等价。最小health不是业务访问的旁路。

复用Hub`frontend/src/shared/cmabSession.ts`，token/user key与母本一致；直接向同源MDM登录/刷新/退出，时长从`/mdm/api/v1/auth/session-policy`读取。401只续一次再重放，403不续期循环；退出和多标签同步沿用母本。当前未改母本，若未来改须盘点副本。

## 观测关联、异常与审计

在已确认存储方案下，设计每轮发布不可变snapshot_id；overview/list/detail/runs/evidence携带该引用，另含inventory_version、rule_version、collected_at、各来源source_observed_at、collection_status、四维状态、reason_codes及evidence_refs。来源时间不同须可见，不保证跨源事务原子一致。

建议旧快照超出保留范围返回410 snapshot_expired，前端明显提示换新视图，不悄悄拼批次。部分源失败仍返回可用部分及失败项；无可用当前观测时返回未知/采集异常，不返回假正常。

task_key/evidence_id/过滤参数严格校验，只引用注册白名单；不接受shell、SQL、任意绝对路径或浏览器提交的源连接参数。时间带时区ISO8601，unknown数值null；公开错误仅code/message/request_id，无DSN、令牌或traceback。

审计范围/位置见ARCHITECTURE、字段见DATA_MODEL。拒绝/失败也留痕；建议审计不可用时证据详情503，不能悄悄跳过；若数据库审计失败，最小脱敏拒绝/失败事件写受控本地审计日志，落库恢复与去重按已确认访问记录范围细化，不能当作GMP合规验证要求。审计及失败关闭已实现，Linux真实读/拒绝请求已写访问记录，自有角色权限通过核验；数据库故障后的本机fallback恢复/去重实测未完成。

## 实际接口补充

POST /api/v1/refresh：仅SYS_ADMIN，202返回update_id，固定全清单只读采集，不接受命令、路径或源结果。GET /api/v1/updates/{update_id}：仅SYS_ADMIN，返回pending/processing/done及完成快照引用。事件接收不是公开HTTP接口，且生产collector拒绝演示模式。

overview/detail可带snapshot_id；缺省为当前视图，积压/应更新后失联会变未知；带引用为不可变历史观测，显示截至时间。runs必须带引用，页100/最多31天，返回total/has_more/cutoff；过期引用410。evidence仅解析该快照最近运行已有证据ID，其他历史证据由有界runs响应提供。API不读任意文件。

当前JSON返回任务、collection_status、state、label、reasons、last_run、next_at及gaps；rule_version/inventory_version/snapshot引用已实现。原四维逻辑与reason_codes属于设计解释，尚未独立编码成全部物理字段；不声称跨来源同时刻事务快照。公开错误不含DSN或traceback。无数据时unknown，审计失败业务读取503。

## D17设备归档兼容字段

2026-11-04兼容增补：Observation增加可空的upstream_risk，包含task_key（本设备归档）、archive_start（原风险批次时间）、past（当时风险说明）与current（截至当前视图的归档说明）。无风险及旧快照默认null；reasons仍保留ETL自身提醒。当前视图按归档采集新鲜度更新current/label，指定snapshot_id仍保持原观测，不补入未来证据。复用JSONB，无结构迁移；新前端兼容字段缺失。

公开任务新增archive_device=vicell/flex2/null；设备Run增加archive_mode=day/night/null及parent_run_id，restore=not_applicable只用于文件归档，不改变MDM验证语义。overview/tasks隐藏内部父来源，公开仍16项；内部父记录可按原key读取，仅SYS_ADMIN。旧snapshot未包含新增设备任务时明确410要求更新，不返回500或拼入未来证据；原结束事件key/UID授权不变。
