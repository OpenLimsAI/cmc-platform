# CLAUDE.md

本文件为 Claude Code 提供本项目的关键操作约定，请遵守。

## 沟通约定
与我的对话用中文，回答尽量简洁、结论优先，避免专业术语。

## 项目概览
CMC LabOps Portal —— 实验室物料库存 + 设备管理系统。
- 后端：FastAPI（`backend/`），端口 **8010**
- 前端：React + Vite + Ant Design（`frontend-react/`），端口 **5110**
- 数据库：PostgreSQL，库 `cmc_data_platform`，schema `material_mgmt`（物料/库存/审计）、`equipment_mgmt`（设备）
- 认证：统一走 MDM Portal 签发的 JWT，无本地用户表

## 部署到生产 Linux（重要）
生产服务器：`ssh -p 13568 prometheus@172.19.0.105`（**已配置免密 ssh**），项目在 `/opt/cmc-labops`。

**已配置 sudo 免密**（`/etc/sudoers.d/cmc-deploy`）：prometheus 可免密执行
`systemctl restart cmc-backend`、`reload nginx`、`restart cmab-backend`、`daemon-reload`。
→ **Claude 可独立完成部署重启，无需向用户索要 sudo 密码，也无需测试摸索 sudo 是否免密。**

**标准部署流程**（本地改动 → 上线）：
1. 本地 `git commit` + `git push origin main`
2. `ssh ... 'cd /opt/cmc-labops && git pull --ff-only origin main'`
3. 前端有改动时：`ssh ... 'cd /opt/cmc-labops/frontend-react && npm run build'`（nginx 静态伺服 `dist/`，build 完即生效）
4. **完整重启后端**：`ssh ... 'sudo systemctl restart cmc-backend'`
5. 验证（在服务器上）：`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8010/health` 应为 `200`

⚠️ **后端必须用 `sudo systemctl restart`（完整重启），不要只热重载。**
原因：时间戳依赖数据库连接时区，热重载会让连接池残留旧连接、写出 UTC 时间，曾污染审计日志历史数据。

服务名：`cmc-backend`（LabOps 后端 :8010）、`cmab-backend`（MDM 后端 :18000）、`nginx`（前端静态 + 反代）。

## 数据库结构变更约定（重要）
对 `cmc_data_platform` 的任何结构性变更（建表/改表/删表、加列/改列/删列、加约束/索引等）**一律通过 `cmc-schema-migrations` 工具（Alembic 版本化迁移）执行并同步到各环境**。
- ❌ 禁止直接在生产/任意库手敲 `psql` DDL，也不要依赖 `sql/init.sql` 改生产结构。
- ✅ `sql/init.sql` 仅用于测试库与本地 dev 初次 bootstrap，**不是生产结构的权威来源**；它要和真实库保持一致，但生产结构以迁移为准。
- LabOps 后端 `cmc_user` 仅有 `material_mgmt` schema 权限，无权做跨 schema 的结构变更——更印证结构变更应走专门的迁移工具，而非应用连接。

**迁移仓库**：`~/code/cmc-schema-migrations`（生产在 `~/cmc-schema-migrations`），统一入口 `./dbmig cmc_data_platform <alembic 子命令>`。

**标准流程**（本机改 → 上线）：
1. 应用要读写新结构时，先改 `backend/models.py`（ORM）+ `sql/init.sql`（建表块 / 末尾"迁移段"加列），保持与真实库一致。
2. 写迁移：`cd ~/code/cmc-schema-migrations && ./dbmig cmc_data_platform revision -m "..."`；编辑生成的 `.py`，写 `upgrade()`/`downgrade()`，DDL 一律带 `schema="material_mgmt"`。
3. 本机落地验证：`./dbmig cmc_data_platform upgrade head`。**破坏性变更（删表/删列）必须 `downgrade -1` → `upgrade head` 往返一次，确认可逆。**
4. 两个仓库各自 `commit + push`：schema 仓一条、cmc-labops 一条。
5. 上线顺序：**加列 = 先 schema 后代码；删列/删表 = 先代码后 schema**。
6. 生产应用：`ssh ... 'cd ~/cmc-schema-migrations && git pull --ff-only origin main && ./dbmig cmc_data_platform upgrade head'`，再核对 `current` 为 head。

> 范例:迁移 `08941b314a8f` 删除废弃表 `app_user`/`auth_session`（upgrade 先删引用方 `auth_session` 再删 `app_user`；downgrade 按 init.sql 原定义复刻重建）。

## 时区约定（重要）
所有 `TIMESTAMP` 列存**裸上海墙钟**（无时区、不存 UTC、显示不换算）。三重保险：
1. ORM 列默认 `default=datetime.now`（应用进程，宿主机时区 = Asia/Shanghai）
2. `backend/database.py` 每个连接 `SET TIME ZONE 'Asia/Shanghai'`
3. 数据库级 `ALTER DATABASE cmc_data_platform SET timezone='Asia/Shanghai'`

新增时间戳列照此写：`mapped_column(DateTime, default=datetime.now, server_default=func.now())`。
**禁止 `datetime.utcnow()`**。本系统单一站点（中国），不考虑跨时区。

## 本地开发（macOS）
- 后端/前端由 LaunchAgent 管理（后端 `--reload`、前端 vite HMR），端口同生产 8010/5110。
- 完整重启本地后端：`launchctl kickstart -k gui/$(id -u)/com.qingcheng.cmc-labops.backend`
- 用 httpx 调外部服务务必加 `trust_env=False`（本机有 SOCKS 代理在 7890）。

## 统一门户 cmab-hub（2026-08-17 起，改前端必读）

- 本系统已挂在统一门户之下：正式入口 **http://172.19.0.105:5100/labops/**（Linux 上本系统前后端只听 127.0.0.1，老端口内网不可达）。Mac 本地同样经 `localhost:5100/labops/`。
- 前端**自己认前缀** `/labops/`：`vite.config` `base:'/labops/'` + `App.tsx` `basename` + `src/shared/base.ts`（BASE/withBase/stripBase/TOKEN_KEY/USER_KEY）。API 一律相对路径 `/labops/api/...`，由门户 nginx 剥掉前缀转给后端（后端路由不变）。**不要**写死 host:端口，**不要**用不带前缀的绝对路径跳转/引资源。
- 登录态用**全公司统一 key**：`localStorage['cmab_access_token']`（MDM JWT）+ `localStorage['cmab_user']`（MDM 登录响应 user 对象）；同源共享 → 门户登录一次这里免登。别再改回私有 key。 跳 MDM 用 `src/shared/mdmPortal.ts`（同源 `/mdm/`）。Linux nginx 片段见 `DEPLOY.md` §4b。
- 门户侧配置/路由/部署脚本在 `~/code/cmab-hub`（`nginx/hub-locations.conf`、`deploy/linux/`），约定见其 `CLAUDE.md`。
