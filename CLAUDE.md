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
