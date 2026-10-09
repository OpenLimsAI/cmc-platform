# Linux 发布说明（当前待首次部署）

2026-10-09 已连接 Linux 做只读前置核查，应用尚未部署。目标主机/实例/端口已初核，启用前再次确认。当前模板使用 `/opt/cmc-water-system-dashboard`、prometheus、后端 127.0.0.1:8015、静态前端 127.0.0.1:5115、Hub `/water/`。

## 启用前置

1. 获得 Git 提交/push 与 Linux 发布授权，创建仓库并记录应用、Hub、QC ETL、MDM、迁移仓库完整 SHA。当前项目没有 Git SHA，模板不能作为发布记录。
2. 核实 Linux 上游水系统 staging 实际数据、规则版本、QC job、只读授权，以及 GMP 日常趋势所需的截止时间和受控快照方案。当前仓储仅支持 Mac staging 契约，**不能直接声称满足 Linux 受控快照要求**。
3. 若需要共享结构，在 cmc-schema-migrations 对应链实现并验证；本次无结构迁移。
4. Linux MDM 建立同名业务角色、审批人员授权，保留既有账号/权限；测试走 MDM 隔离流程。Mac 角色不自动同步 Linux。
5. 在受保护 `backend/.env` 配置 Linux 只读 DSN、MDM 验签算法/密钥、角色白名单、`APP_ENV`、`PNG_FONT_PATH`。密钥不放服务文件，不输出。RS256 使用 PEM 公钥，多行值按 dotenv 引号处理。字体必须指向已安装、允许使用的中文字体，并实际导出检查。
6. 核实 8015/5115 未占用、Hub `/water/` 无冲突、回环绑定和文件权限。创建可写的 logs/matplotlib 目录。安装 systemd/nginx 需明确发布授权。

## 固定提交构建

遵循 Mac → GitHub → Linux。Linux 拉取已授权的目标提交后：

```bash
bash deploy/linux/prepare.sh <完整40位SHA>
```

只做锁定依赖构建，不安装服务。先验证中文字体、实际业务抽样、API 两档权限、三类导出和失败场景，再安装 `water-backend.service` 与 `water.conf`；Hub 同步已审核的 apps.ts / hub-locations.conf，执行 nginx 检查及按所属项目流程重载。

## 回滚与验收

记录并保留前一个应用/Hub 固定 SHA、构建和服务配置。出现问题先停止业务入口，再切回同一仓库旧提交并重建/重启；本次无数据迁移，不需要删除或回写源数据。保留已有角色，人员撤权按 MDM 审批流程操作，旧 access token 的有效期不因本地按钮隐藏消失。

验收必须重新执行 docs/09，核对实际前端资源、深链、身份刷新/退出、只读数据对账、受控数据上下文、PNG 中文、Excel 原值和组合包，不能沿用 Mac 数字或健康接口作为 Linux 通过证据。


## 已准备的部署入口

`bash deploy/linux/deploy.sh <完整40位SHA>` 在构建及环境/字体检查通过后备份并安装水看板systemd/nginx配置，启动服务并检查本机端口。MDM健康路径按现有MDM发布脚本核对为Hub同源 `/mdm/api/v1/health`。nginx检查失败自动恢复本脚本改动的配置；应用启动失败则保持错误退出，须按前述固定版本回滚。它不会覆盖Hub仓库文件或建立角色；须事先按Hub/MDM所属流程同步配置和授权。此脚本仅在Mac进行静态检查，未在Linux执行。

Linux环境模板为backend/.env.linux.example，须替换受保护凭据和实际已安装字体路径，不把示例字体路径当安装事实。首发仍须完成点位来源、真实身份、数据及受控快照用途前置检查，不能仅凭pull/build宣布业务上线。


## 2026-10-09 前置核查

本地 Git 已初始化并完成首次提交，尚未推送。用户指定 GitHub 仓库已通过 SSH 成功访问；HTTPS/gh 未登录。首次提交＋推送被自动审查拒绝，因包含真实验收截图及业务数据痕迹，仓库隐私及外发范围未明确；本地提交单独成功，推送等候用户选择脱敏或允许完整材料。

Linux Hub 827201d159da65479801cf119483e49b837ec606 已有 water 注册及代理；8015/5115 无监听，water-backend inactive。lims_reader 查询允许、业务写入禁止；staging 最新装载为 2026-10-09 04:00:20+08:00，抽样日期已纠正。MDM 当前未查到两档业务角色；没有调整任何人员授权。

新增 configure.sh：已有有效只读配置与 MDM 保护配置复用，仅生成0600的应用.env；不覆盖既有配置。先核对字体安装，再执行 `bash deploy/linux/configure.sh` 和明确SHA的deploy.sh。Linux uv位于用户.local/bin，prepare已加入PATH。配置脚本目前仅静态验证，尚未在Linux执行。
