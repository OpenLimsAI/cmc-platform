# 08 · 开发、部署与运维

> 版本：0.6｜日期：2026-10-09｜状态：现行运行/发布约定；日期化执行结果见 STATUS/releases。

## 1. 当前入口与工具链

Mac目录/Users/qingcheng/code/cmc-water-system-dashboard，入口http://localhost:5100/water/；Linux目录/opt/cmc-water-system-dashboard，入口http://172.19.0.105:5100/water/。SSH按全局入口prometheus/13568核对，后端8015、前端5115均回环。服务发布已有记录，本轮未重连，不把旧“空表/无服务”的记录当现状。

本地安装启动和验证命令见README。Python用uv锁文件，前端pnpm。Mac start.sh检查端口占用后启动uvicorn和Vite，日志写logs/；保持终端运行，Ctrl+C停止本次两个进程，任一个退出会停止同伴。仓库没有LaunchAgent安装步骤，不推断系统上实际托管状态。

Linux用water-backend.service常驻uvicorn，nginx water.conf伺服前端dist；Hub由独立仓库维护。操作步骤以 [Linux说明](../deploy/linux/README.md) 为准。

## 2. 实际配置项

| Settings字段/环境键 | 约束与默认 |
|---|---|
| app_env / APP_ENV | 默认mac_dev；Linux部署脚本拒绝mac_dev，生成配置为linux |
| database_url / DATABASE_URL | 必填分析库asyncpg连接；真实值仅backend/.env |
| jwt_algorithm / JWT_ALGORITHM | HS256默认或RS256，与MDM一致 |
| jwt_verify_key / JWT_VERIFY_KEY | 必填验签密钥或PEM公钥；无独立公钥路径配置 |
| water_view_roles / WATER_VIEW_ROLES | 必填逗号角色码集合，非空合法 |
| water_export_roles / WATER_EXPORT_ROLES | 必填且是查看角色子集 |
| staging_data_origin / STAGING_DATA_ORIGIN | unverified默认、legacy_xlsx或oracle_etl；依据实际staging装载证据设置 |
| png_font_path / PNG_FONT_PATH | 默认Mac STHeiti路径；Linux填已安装允许使用的中文字体，路径存在还需导出视觉核对 |
| max_rows / MAX_ROWS | 默认100000，配置允许1–1000000；不是批准容量 |

Settings读取backend/.env、忽略未知环境键。APP_BASE_PATH/APP_TIMEZONE没有配置项；路径/water/和时区Asia/Shanghai在代码固定。后端端口写于启动命令/systemd，前端Vite strictPort。日期跨度3660天、SQL超时30000ms和application_name=water_dashboard在代码固定。环境模板仅占位，不复制真实凭据到仓库。

configure.sh仅首次生成0600配置；存在.env时拒绝覆盖。它读取Linux已有QC只读DSN和MDM保护配置，仅支持自动复用HS256；RS256需按现行设置核对并安全配置，不能把该脚本当通用算法自动迁移器。模板字体路径与安装环境可能不同，以实际文件核对。

## 3. 发布边界与前置

1. 核对授权、各仓库完整SHA、工作区及备份/恢复路径。按Mac→GitHub→Linux获取同一业务提交，不手工复制源码绕开版本。
2. 核对分析库结构、五表只读授权、数据/规则和QC作业；实际数据到位与代码发布分开。看板不启动ETL、不读取Oracle、不复制Mac业务数据。
3. 本项目当前发布没有结构迁移。若后续有共享结构，另走cmc-schema-migrations明确revision；MDM自身结构归MDM迁移链，不重复迁移。
4. 身份白名单、MDM角色配置、人员授权与真实身份验证分别登记。既有服务可用于受限验证；正式业务用途不能跳过未完成的验收与OP-06/08。
5. 上游调度按QC ETL当前配置和运行台账核对，本项目不复制历史08/12/16时点或新建调度。context当前未查job，始终提示新鲜度未核实。
6. Hub注册、同源MDM、回环监听、中文字体和实际静态资源均需验证；健康200不代表角色/数据/下载验收通过。

## 4. 脚本与回滚的实际行为

prepare.sh验证HEAD等于完整40位SHA、工作区干净、backend/.env存在，再uv/pnpm锁定依赖构建；不拉代码、不切提交、不执行迁移。

deploy.sh调用prepare、检查非Mac环境和字体路径、检查Hub同源MDM健康；备份已有unit/nginx配置后安装本项目配置。nginx-t失败恢复本脚本改动并退出；通过后启用/重启后端、检查active和health、reload nginx并检查静态入口。脚本不创建业务角色、不改Hub源码、不验证两档身份或数据一致性。

应用启动/后续检查失败不会自动恢复旧代码和dist；构建直接写当前dist，发布不是原子切换。发布前须另保存旧固定SHA/构建/环境保护配置及恢复方案。失败时按实际阶段停止依赖该步骤的业务启用，切回原仓库旧SHA重建/重启并核对Hub兼容；不自动downgrade或删除数据。无数据库变更的代码回滚不需要回写源结果。

## 5. 运维、证据与跨仓库关系

Linux服务为water-backend，日志为journalctl -u water-backend；MPLCONFIGDIR为项目logs/matplotlib，配置备份在logs/deploy-日期时间。Mac日志为logs/backend.log及frontend.log。检查身份拒绝、业务查询、Hub资源、只读授权和QC job状态，不能仅检查health。

日期化发布记录采用docs/releases/，功能变更采用docs/changes/，已公开摘要与本地敏感证据分开；本次既有发布叙述移至 [2026-10-09记录](releases/20261009-linux.md)，级联细节保留原changes记录。后续记录主机/时间/执行人、完整SHA、配置变化、迁移/data版本、实际查询/权限/文件/浏览器结果、备份/回滚和未关闭项，并更新STATUS。

同级跨项目链接用于开发检出；Linux使用/opt实际仓库和固定版本，不执行Mac路径。依赖版本/文档缺失时从对应仓库受控版本取得，不把静态链接当部署证据。

参考：[PORTS](../../PORTS.md)、[Hub说明](../../cmab-hub/nginx/README.md)、[迁移README](../../cmc-schema-migrations/README.md)、[迁移SOP](../../cmc-schema-migrations/SOP.md)、[QC运维](../../qc-lims-etl/docs/05-ops-deployment.md)。
