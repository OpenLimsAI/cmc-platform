# MDM 与 PM 第一阶段真实端到端验收

2026-10-26，执行主机 ThinkpadT14-Le。结果：实际浏览器成功完成门户登录、独立 MDM 登录、已有项目一对一绑定、刷新持久化、两端上下文往返和权限/冲突拒绝。自动测试与真实验收分别记录。

## 真实环境与数据隔离

|组件|验收期间地址或资源|隔离依据|
|---|---|---|
|门户与 PM 前后端|`http://127.0.0.1:5189/`|实际生产构建的 SPA + FastAPI，启用真实 API、实际 OIDC；本机同时展示门户/PM使用 combined 前端构建，不依赖正式域名|
|MDM 前端|`http://127.0.0.1:5188/mdm/`|实际 React/Vite，通过代理调用独立后端，MDM 原生密码鉴权|
|MDM 后端|`http://127.0.0.1:18088/api/v1/health`|实际 FastAPI、迁移到0066，无运行时依赖替换|
|Casdoor|`http://127.0.0.1:8018/`|官方 `casbin/casdoor:3.100.0`，新组织 `phase1-e2e`，全新签名证书；本地 PM/门户两个独立客户端和回调|
|数据库|`cmc-phase1-e2e-postgres`|新建 PostgreSQL 16，数据目录 tmpfs；`mdm_phase1_e2e`、`pm_phase1_e2e`、`casdoor_phase1_e2e` 三个独立新库及不同应用角色；不发布数据库端口|
|缓存与网络|`cmc-phase1-e2e-redis`、`cmc-phase1-e2e-net`|专用网络与新缓存；所有对宿主机发布端口明确绑定127.0.0.1，未修改防火墙或网络安全设置|

没有连接已上线 MDM dev 库或现有 PM/Casdoor 数据；没有真实仪器、NAS、ETL、Hub 改动。只初始化新测试库的结构和原生基线身份，不灌业务演示数据。PM `AUTO_SEED=false`、信息获取 worker 关闭。浏览器内项目均通过真实表单创建，无 mock 数据仓库、dependency override 或绕过登录。

合成身份：Casdoor `phase1.admin`（项目负责人）、`phase1.reference`（仅两个验收项目成员、无任务）、`phase1.outside`（无项目范围）；MDM 新库原生 `admin`、`readonly`。没有给真实员工改角色。核验身份是普通 PM 用户，可能拥有自身范围内写权限，不是正式只读机器身份。

用户明确批准后，通过 Casdoor 与 PM 现有嵌入式授权码流程取得临时 PM audience 访问令牌：S256 PKCE、state、nonce、JWT签名、issuer/audience、有效期及实际项目范围均检查。最长一小时、无自动续期，令牌只经内存管道进入隔离 MDM 子进程环境，不写文件/日志/聊天/URL，不转发 MDM JWT。此前被自动审批拒绝的会话数据库解密提取命令未执行；没有改用浏览器存储或数据库间接提取。

## 验收项目

|登记项目|MDM编号|PM编号|PM保留的原始ID|
|---|---|---|---|
|隔离验收登记项目 A|`CMAB-PRJ-2026-0001`|`PHASE1-E2E-A`|`pu-mvp5fhtx-6t6q5`|
|隔离验收登记项目 B|`CMAB-PRJ-2026-0002`|`PHASE1-E2E-B`|`pu-mvp5h6kz-oif72`|

MDM保留bigint登记ID，PM保留字符串ID，没有按名称匹配或覆盖任一端ID。

## 实际浏览器步骤与结果

|步骤|实际结果|截图|
|---|---|---|
|门户真实登录，进入PM独立客户端会话|实际负责人身份，界面创建空白执行项目 A/B，无任务模板|[门户](01-portal-authenticated.jpg)、[执行项目A](02-pm-project-a.jpg)|
|门户 MDM 卡片进入独立登录|进入 `/mdm/login?redirect=...`，使用MDM原生身份，界面新建登记项目 A/B|[独立登录](03-mdm-independent-login.jpg)|
|配置核验身份前提交|实际503，未写映射|[安全默认拒绝](04-verifier-not-configured.jpg)|
|PM未关联项目上下文|正确携带PM B的ID；MDM登录后明确未关联，不猜测同名项目|[未关联上下文](08-pm-to-mdm-unlinked-context.jpg)|
|MDM A手动提交准确PM A ID及原因|后端实际核验PM后成功，显示实时编号/名称/状态与创建快照|[已核验](09-mdm-bound-verified.jpg)|
|刷新，离开详情后重新打开项目地址|同一关联ID、核验建立时间和目标项目保持，实时核验仍成功|[刷新](10-mdm-bound-after-refresh.jpg)、[重新进入](15-mdm-reentered-persistent.jpg)|
|点击打开PM A，再点MDM上下文按钮|实际打开PM A执行项目，再解析回MDM登记A；URL不含令牌/身份|[PM A](11-mdm-to-correct-pm-a.jpg)、[返回MDM A](12-pm-context-resolved-mdm-a.jpg)|
|MDM B抢占PM A，随后正确绑定PM B|抢占被拒，表单保留错误；随后B→B实际成功|[冲突](13-mdm-one-to-one-conflict.jpg)、[B已绑定](14-mdm-b-bound-correctly.jpg)|
|查看MDM A审计|只一条关联CREATE审计，记录原生数字用户身份、原因和请求ID；另有原项目创建审计|[关联审计](16-mdm-single-link-audit.jpg)|
|MDM readonly实际登录|未关联时无绑定控件；关联后可看实时摘要且仍无绑定/改绑控件，现有审批权限未放宽|[无控件](06-mdm-readonly-no-bind-control.jpg)、[只读摘要](17-mdm-readonly-linked-summary.jpg)|
|无PM项目范围身份实际登录|绑定前/后都不能读项目或打开上下文接口；映射没有授予PM访问权|[绑定前](07-pm-outside-project-denied.jpg)、[绑定后页面](18-bound-project-still-denied-to-outsider.jpg)、[绑定后接口](19-bound-context-api-denied.jpg)|

所有截图只包含合成身份/数据。冲突与503的界面沿用现有通用错误提示，具体HTTP状态另通过实际服务响应核实，没有将通用提示冒称为完整错误详情。

## 实际 HTTP 与持久化补充核对

这些请求使用实际服务和原生密码登录取得的同应用身份，不是测试客户端或鉴权替换；它们补充上述浏览器链路。

|行为|真实响应|
|---|---|
|相同 A→A 连续重复两次|200、200，原关联内容与时间不变|
|同一个MDM A改指PM B|409|
|MDM B抢占PM A|409，B在正确绑定前仍为空|
|不存在的PM目标；不存在的MDM登记项目|404、404|
|匿名写关联；readonly写关联|401、403|
|readonly读已关联摘要；反向解析PM A|200、200，解析到登记A|
|无PM项目范围实际浏览器会话调用引用/上下文接口|404，服务访问日志确认|

数据库只读计数：映射总数2、不同MDM ID数2、不同PM ID数2；成功关联审计总数2。重复和冲突未增加审计。MDM两项目仍为proposed，PM两项目仍活跃/进度0，任务0；预算与计划没有由映射链路复制。运行时代码只有MDM映射事务，没有跨库业务直写。

## 自动化验证与 TDD

- PM接口9项、门户卡片2项：先失败后实现通过。门户保护入口测试发现缺少响应导入，修复后通过。
- MDM部分实现早于首次有效测试；初次有效运行前遇到CRLF、缺curl与审计角色夹具问题，不声称全程先测。之后总响应截止时间、项目审计可见性先失败再修复。
- PM finance控制字符lint最小等价修复有34项回归；信息页立即卸载首次请求测试red→green。
- Thinkpad Docker Linux：PM后端413项、原指定覆盖率93.94%；前端274项，原逐文件90%覆盖率门槛通过；eslint、后端84文件格式、类型检查、构建通过。Windows直接全量运行有Linux `resource` 依赖和覆盖率计时限制，未放松原5秒超时/断言；相同Linux等效环境通过。
- MDM容器内81项相关项目/状态/团队/审计/就绪测试、新代码ruff/mypy、前端锁定安装/eslint/类型/构建通过；不是MDM全仓全量测试声明。迁移空库→0066、两侧DB唯一约束、并发与非空降级拒绝均有回归。
- PM原全仓ruff lint含存量FastAPI B008报告；CI按既有软检查规则报告，不宣称后端全仓lint零告警，没有降级规则。最终合并依据两仓最新head全部适用CI与上述真实E2E。

PR：[PM #46](https://github.com/OpenLimsAI/mb-pm/pull/46)、[CMC #1](https://github.com/OpenLimsAI/cmc-platform/pull/1)。CI纯测试/构建，未发现合并触发生产部署；先PM后MDM合并，正式部署和正式机器身份不在本次授权范围。

## 撤销、停止与恢复边界

验收后清除MDM子进程中的核验令牌，先验证已有映射仍在、状态变为not_configured且不再提供未经核验的深链；再禁用3个合成Casdoor身份和2个使用过的MDM身份、撤销MDM刷新会话并使隔离PM/门户会话过期，正常退出浏览器PM会话。停止本次隔离服务与相关测试容器，不停止原有预览或其他Docker服务。实际完成结果见[清理记录](cleanup.json)。

以上地址仅在验收期间运行；清理后不能再当作在线演示链接。测试数据库使用tmpfs，停止即失去本次合成数据，不复用该停止实例冒充可恢复环境。后续演示需重新建立隔离实例与临时身份，再按步骤创建新测试数据；不从生产恢复，也不重建未知库。本次没有删除未知或原有数据。

应用回退优先清空新增入口/核验配置并保留真实映射。0066有映射时拒绝降级删表；旧代码迁移版本就绪约束要求协调回退，禁止stamp绕过。本次验收身份/令牌不可用于正式环境；正式只读机器身份及续期、解除/改绑流程、统一SSO和Hub退役仍是后续工作。
