# 本机真实跨系统浏览器回归

2026-11-03 后续补验使用 `regression-plan.mjs`，把空库两阶段签署及历史故障恢复变成下列有界入口。此前单调用失败记录保留，最终是否通过以对应新轮报告为准。

## 分阶段入口（受支持浏览器工具）

按下文初始化新 run、生成合成 fixture、启动 `exercise` 后，在已选择并命名的 CUA 浏览器中：

```js
var driver=await import(driverFileUrl); // frontend/e2e/fixture-driver.mjs
var planModule=await import(planFileUrl); // frontend/e2e/regression-plan.mjs
var portal=await browser.tabs.new();
var plan=await planModule.createRegressionPlan({browser,portal,directory:runDir,fixture,runKey:'UNATTENDED-UNIQUE'});
await plan.phaseOne(); // 必须返回awaiting-confirmation；真实登录、创建关联、内嵌验密
```

下一次独立 CUA 调用：

```js
await plan.phaseTwo(); // 自动确认提交，验证1份签名/历史/PM receipt真实落库
```

每个后续入口也用一次独立、有界 CUA 调用顺序执行：

```js
await plan.prepareRecovery(); // 新登记项目；注入一次本地关联提交失败，PM真实创建
await plan.finishRecovery(); // 自然等待原30秒租约到期，浏览器双击重试原请求
await plan.restartApplications(); // 只重启应用进程，三应用会话和关联持久性
await plan.transientOutage(); // 表单内真实502，保留会话/输入，服务恢复后再开真实认证页
await plan.finish(); // 验证2项目/2关联/2receipts、1签名/历史，写终态触发清理
fixture=null;
```

这些是受支持工具的分阶段调用。是否可自动输入密码须服从当前工具反馈和授权；若受阻则安全交接，不能绕过或宣称无人值守通过。不在一个长调用内紧接 iframe 成功就点击确认。每步会记录 `case-results.jsonl`。任何 blocked/安全停止/未知结果都会阻止后续步骤，不自动重复写入；可用 `plan.abort()` 仅封存失败并请求已有隔离资源清理，不再操作浏览器。

页面上下文必须沿实际“PM→MDM”返回标签继续。驱动保存并核验该标签ID与确切项目URL，不退回旧的同项目标签。`activeProjectTab` 的正向和URL变化拒绝均有单测。

### 故障控制边界

`fixture-driver.mjs` 只通过本轮 `control/` 目录发送有限JSON，CLI `e2e_control.py` 验证完整资源ID、标签、ready阶段和新建tmpfs库。仅支持snapshot、fault-next-link、stop-mdm、start-mdm、restart-apps，不接受SQL、shell、任意路径/账户/权限操作。

- 一次性触发器只针对观察到的未关联、尚无创建请求的合成项目。序列计数不随失败事务回滚；远端真实receipt保留，本地首次关联提交失败。重试验证原request ID/PM ID、attempts=2，远端项目数量不变。
- 不缩短/改写30秒租约。先记录remote_created状态，后一步由正常UI等待可重试按钮。
- 重启只SIGTERM唯一匹配的容器内uvicorn进程，原数据库/IdP不重启，配置密钥不轮换。进程不唯一则拒绝。
- 短暂MDM停机最多45秒，有自动恢复兜底；正常场景主动恢复。通过真实表单提交遇到502验证UI保留，再恢复到真正Casdoor iframe。没有伪造HTTP响应或替换应用依赖。
- `test_e2e_control.py` 8项先实际red再green；与环境护栏共17项，相关后端最终142项通过。两个返回标签护栏在修复后补写，不伪称先测证据。

这些本地新文件尚未提交，也未推送或触发远程CI。后端CI显式测试清单已加入控制护栏，前端`test:unit`可发现新增测试；真实CUA浏览器场景仍是本地工具适配器流程，不能称GitHub Actions已运行它。

这些文件属于 MDM 工程。`joint-scenarios.mjs` 是受支持 CUA 浏览器适配器的场景代码，不是 mock、HTTP 登录替身或独立签名 PoC。当前仍在本地未提交分支，未进入 main/CI。

## 环境边界

- 仅 Thinkpad 本机，固定 `127.0.0.1:19081/19090/19091/19092`，分别为 IdP/MDM/PM/门户。
- 默认 `official-v4` 使用固定官方 v4.25.0 作协议对照；最终受限客户端联测必须在 up 时显式选择 `--identity-profile restricted-v11`，使用已校验的本地 v11 补丁镜像。两个固定镜像见 `backend/scripts/e2e_services.py`，不接受任意目标。
- 每次使用唯一 `mdm-e2e-*` run ID、内部 Docker 网络和全新 tmpfs PostgreSQL；不接受已有库或真实用户。
- 两名合成用户 `e2e.signer`、`e2e.other`；五个明确命名的 DCR 客户端。仅授权码，令牌和 IAM Cookie 最长一小时，无自动刷新。MDM 管理/只读与 PM cmc_lead/rd 角色只作用于该空测试库。
- 签名模式 `oidc_fresh`，原生登录关闭。保留过期的旧本地签名口令标记，用于验证新模式不再受该旧门槛阻断；不篡改历史签名。
- 只能使用新生成的测试密码。禁止读取真实密码、导入 Cookie、预置已登录浏览器状态、关闭鉴权或强制放行暂停文档。

## 前置条件

Docker Desktop；宿主 Python 3.11+ 仅运行标准库生命周期脚本；后端测试工具在容器内。MDM 和 PM 必须是各自的本地 checkout，PM 含 `CASDOOR_ACCOUNT_STATUS_MODE=casdoor_v4_self_policy` 的兼容代码及测试。

本轮使用已有依赖缓存镜像 `mdm-phase2-unit-tests:latest`、`cmc-pm-phase2-e2e:local`、`cmc-mdm-phase2-frontend:local`、`cmc-pm-phase2-fe-verify:local`，以及 PostgreSQL 16、Redis 7、nginx 1.25。框架不会自动安装/拉取未知依赖；没有这些缓存时应按仓库锁文件先构建验证镜像，并核对版本。镜像实际 ID 会进入证据。

新机器的缓存构建入口（本轮使用既有缓存，未另做一轮在线拉取验证）：

```powershell
# 从 MDM 工程根目录
docker build -f deploy/test/backend.Dockerfile -t mdm-phase2-unit-tests:latest backend
docker build -f deploy/test/frontend.Dockerfile -t cmc-mdm-phase2-frontend:local frontend
# PM 后端及前端依赖缓存；修改为实际 checkout 路径
docker build -t cmc-pm-phase2-e2e:local C:\path\to\mb-pm\backend
docker build -f backend/scripts/e2e_assets/pm-frontend-cache.Dockerfile -t cmc-pm-phase2-fe-verify:local C:\path\to\mb-pm
```

只从 Docker 官方基础镜像/仓库锁文件所用正常包仓库构建。MDM Python 用 `uv.lock`、MDM 前端用 `pnpm-lock.yaml`、PM 前端用 `package-lock.json`，PM 后端沿用其固定 requirements。不迁移包管理器。

## 初始化与执行

从 `cmab-mdm-platform/backend` 执行，例中的 PM 路径换成独立本地工作树：

```powershell
python -m scripts.e2e_runtime prepare --run-id mdm-e2e-example --pm-root C:\path\to\mb-pm
```

`prepare` 只创建空的内部基础设施。产物位于 `cmab-mdm-platform/.local-e2e/<run-id>/`，已被 Git 忽略。`fixture-public.pem` 是临时公钥；私钥留在 tools 容器 tmpfs。

使用支持的 `cua_repl` 驱动生成两份一次性密码，在驱动内存保留以下形状的对象，不输出密码：

```js
var fs = await import('node:fs/promises');
var crypto = await import('node:crypto');
var fixture = {syntheticOnly:true, users:Object.fromEntries(
  ['signer','other'].map(k=>[k,{username:'e2e.'+k,password:crypto.randomBytes(24).toString('hex')}]))};
var sealed = crypto.publicEncrypt({key:await fs.readFile(runDir+'/fixture-public.pem'),
  padding:crypto.constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},Buffer.from(JSON.stringify(fixture)));
await fs.writeFile(runDir+'/fixture.sealed',sealed);
```

这里只在磁盘写密文，不通过聊天或明文文件传递密码。随后：

```powershell
python -m scripts.e2e_runtime import-fixture --run-id mdm-e2e-example --sealed-fixture ..\.local-e2e\mdm-e2e-example\fixture.sealed
python -m scripts.e2e_runtime exercise --run-id mdm-e2e-example --pm-root C:\path\to\mb-pm --await-seconds 1800
```

`exercise` 用实际源码离线构建前端，迁移三个新库、显式映射合成身份、启动真实服务，等待浏览器结果；最终路径均调用清理。运行中从另一执行单元操作 CUA：先选定/命名浏览器、读取文档、打开一个新的本机门户页，然后导入 `joint-scenarios.mjs`。将 `browser`、`portal`、内存 `fixture`、唯一 `runKey` 和保存真实截图的 `capture(tab,name)` 交给 `runJointCases`。截图回调应同时写时间、场景、版本和 SHA-256，不能输出秘密。

```js
var cases = await import(moduleFileUrl);
var result = await cases.runJointCases({browser,portal,fixture,runKey,capture});
// result.status === 'awaiting-confirmation' means authentication is verified,
// not signed yet. Observe this result and perform the next call in a NEW CUA cell.
```

下一次 CUA 调用：

```js
if (result.status === 'awaiting-confirmation') {
  var signingTab = await browser.tabs.get(result.mdm_tab_id);
  await cases.confirmVerifiedSignature({mdm:signingTab,capture});
  result.cases.push({name:'fresh-embedded-signature',status:'passed',time_utc:new Date().toISOString()});
  result.status='passed';
}
await fs.writeFile(runDir+'/browser-result.json',JSON.stringify(result,null,2));
fixture=null;
```

本轮三次实测，同一 CUA 调用中紧接 iframe 成功就点击确认未观察到提交；重新观察后的独立调用成功。已采用上述两阶段适配，不要求人工输入或手动确认。未将这一工具时序现象归因为业务缺陷，也未调整安全校验。旧单调用失败记录仍保存；不得称其无人值守 CI 已稳定通过。

结果文件触发只读业务断言快照和清理。**不要在截图/必要断言完成前写终态结果。** 如果浏览器被停止或文档被安全暂停，应立即终止该 UI 场景，记录 blocked，不能改用 raw CDP、其他驱动或 Cookie 注入。此文件不是可脱离 CUA 工具政策运行的浏览器客户端。

## 清理与中断恢复

```powershell
python -m scripts.e2e_runtime status --run-id mdm-e2e-example
python -m scripts.e2e_runtime snapshot --run-id mdm-e2e-example --pm-root C:\path\to\mb-pm
python -m scripts.e2e_runtime cleanup --run-id mdm-e2e-example
```

清理严格校验 ledger 的完整资源 ID 与 run 标签，拒绝有外来成员的网络/卷；仅移除该次明示可销毁的合成库、容器、网络。未知创建结果记在 `pending_action`：先只读对照实际 Docker 状态，不要重复 provision，也不能盲目清空标记。`cleanup-receipt.json` 记录删除范围及四端口是否仍在监听。剩余监听可能属于另一个进程，只报告，不停未知进程。

## 分层回归与验收范围

```sh
# 仅在全新隔离 cmab_test 中，由仓库 runner 执行后端测试
docker exec <owned-tools> bash /test-runtime/run_tests.sh tests/test_e2e_runtime_safety.py -q
# 前端容器
pnpm test:unit
pnpm lint
pnpm build
```

`test:unit` 包含深链 URL 限制及安全停止后不继续输入/截图的护栏测试。它们不等于浏览器验收。`backend/scripts/run_phase2_tests.py` 和 `deploy/test/frontend.Dockerfile` 已纳入新测试入口；未推送，不能声称远程 CI 已通过。

当前场景：门户实际登录→MDM SSO→创建登记项目→当前用户委托→双击创建 PM 并关联→真实 PM 详情→回到 MDM→刷新保持关联→内嵌再次认证→独立调用确认签署。还有可单独调用的 `negativeSigningCases` / `cancelProofKeepsForm` / `rejectOtherIdentity`，以及候选 `rpLogoutCurrentBrowser`。这些代码仍需遵守每一步实际观察和工具停止规则；每项以本轮报告和结果为准，blocked 不算通过。

此前还实测过远端已创建/本地落库失败的同请求恢复、409 冲突、只读权限、应用进程重启和 DCR 统一退出失败。这些旧证据在 `docs/verification/oidc-signing-local/joint-portal-pm-20261103/`；尚未全部转换为本适配器的可调用场景，不能把一次性旧脚本或手工步骤称为已自动化。

2026-11-03 新轮正常初始化后，签名 iframe 已真实加载，完成再次验密、三份业务签署和错误密码/取消/不同账号拒绝，没有强制放行暂停文档。此前暂停原因仍未知，不保证不会再次出现。官方 RP 退出通过既有 DCR 客户端已使当前浏览器 MDM/PM/门户回到登录，并要求 IdP 重新输入凭据；尚未接入产品按钮，不等价所有设备退出。v4 改密后旧 IAM Cookie 撤销仍未与现有补丁等价。正式升级仍需解决这些安全差异，不能用普通客户端的隐含管理权限替换 DCR 来换取通过。


## 最终受限环境的显式入口

```powershell
python -m scripts.e2e_runtime up --run-id mdm-e2e-example --pm-root C:\path\to\mb-pm --identity-profile restricted-v11 --password-only-signature
```

prepare、fixture 导入与清理仍按上文步骤执行；`restricted-v11` 只设置原两合成用户、五个回环客户端和精确的本人策略／退出能力，不变更既有身份实例。先单独确认此次临时凭据及权限操作的授权，不能仅凭运行脚本自动获得许可。相同 run 不允许更换身份 profile。

本仓库不包含原体验环境的受限 fixture、密钥、旧密码读取助手或浏览器会话。不能用接口登录、注入 Cookie、解除安全暂停或已有截图代替新浏览器验收。CI 执行单测／构建与运行浏览器场景是不同覆盖层级。`--password-only-signature` 仅为新建合成签名客户端应用已测官方展示设置，不改 grant／密钥／其他客户端。默认不启用。最终同一候选尚未全部无人值守签署，历史人工签名证据及审计直接外键缺口见 docs/verification/pr-candidate-20261105/report.md。
