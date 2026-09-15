# CMAB MDM Portal IQ 安装确认清单（P4.D-1）

| 项目 | 内容 |
|---|---|
| 文档编号 | IQ-MDM-001 |
| 版本 | V2.0（**原生部署形态**；V1.0 为 docker-compose 形态，见 §0 说明） |
| 适用 | UAT / 生产首次部署 + 升级部署 |
| 合规 | GAMP 5 Cat 4 / 21 CFR Part 11 §11.10(b) 系统验证 / EU Annex 11 §4 |
| 执行人 | IT 安装工程师 |
| 复核人 | QA / CSV 验证工程师 |

---

## 0. 执行说明

- **部署形态：Linux 原生（venv + systemd + 宿主机原生 PostgreSQL / Redis / nginx），不是 Docker。** 本清单 V2.0 据此编写。
  - 后端：systemd `cmab-backend.service`（venv `uvicorn app.main:app --port 18000`）
  - 前端：宿主 nginx `listen 15173` → 伺服 `/opt/cmab-mdm-platform/frontend/dist`，`/api` 反代 `127.0.0.1:18000`
  - 数据库：宿主机**原生 PG16 集群 `mdm` :5433**，库 `cmab_mdm`、用户 `cmab_app`（同机另有 LabOps 用的 PG 集群 :5432，互不相干）
  - Redis：宿主机原生 `redis-server`
  - 目录 `/opt/cmab-mdm-platform`，运行身份 `prometheus`；部署/升级用 `bash deploy/deploy.sh`
  - 权威记述：README §部署 + `deploy/deploy.sh` 头部注释 + `docs/RUNBOOK_*`
- ⚠️ **仓库内 `deploy/docker-compose.prod.yml` + `deploy/nginx/*` 是另一套 docker-compose 生产形态（可选/模板，含 TLS 网关），不代表本服务器实际。** 若改用该形态部署，使用本仓库历史版 V1.0 IQ（git 可取）。
- 本清单每一行都必须填写 **执行结果**（PASS/FAIL/N/A）+ **执行人签名** + **日期**
- 任何 FAIL 项必须有偏差说明（CAPA 单号或同等记录），整改后重测
- 完整执行记录（含本表 + 命令输出）归档到 GxP 文档管理系统，保留 ≥ 7 年
- 每次升级部署只需重跑变化项（标 ⚠️ 的必跑）
- 命令中 `psql` 默认带 `-p 5433`（MDM 集群）；如本机用 `PGPORT`/`.pgpass` 已固化可省略，但须先确认连的是 `mdm` 集群而非 :5432

---

## 1. 操作系统与运行时基线

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 1.1 | 主机 OS | Linux x86_64（Ubuntu 22.04 LTS 或 RHEL 8+） | `uname -a` | ☐ |
| 1.2 | 主机 OS 时区 | `Asia/Shanghai`（备份 timer 的 02:00 按本地时区解释） | `timedatectl status` | ☐ |
| 1.3 | systemd 可用 | 托管 cmab-backend / nginx / postgresql / redis | `systemctl --version` | ☐ |
| 1.4 | 部署目录与属主 | `/opt/cmab-mdm-platform` 存在，属主 `prometheus` | `stat -c '%U %n' /opt/cmab-mdm-platform` | ☐ |
| 1.5 | 磁盘空间 | 数据盘 ≥ 100 GB 可用（PG 数据目录 + 备份目录所在盘）| `df -h /var/lib/postgresql ${BACKUP_DIR:-/home/prometheus/cmc_backups/mdm}` | ☐ |
| 1.6 | 主机防火墙 | 仅放行对外访问端口（HTTPS 前置或 :15173），内部 :18000/:5433/:6379 不对公网 | `iptables -L -n` 或 `firewall-cmd --list-all` | ☐ |

## 2. 中间件版本（宿主机原生）

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 2.1 | PostgreSQL | 16.x，集群 `mdm` 监听 :5433 | `psql -p 5433 -U postgres -tAc "SHOW server_version"` | ☐ |
| 2.2 | PG 集群服务托管 | systemd 管理、开机自启 | `systemctl is-enabled postgresql@16-mdm`（或本机集群单元名）| ☐ |
| 2.3 | Redis | 7.x，原生 `redis-server` 运行中 | `redis-cli -p 6379 INFO server \| grep redis_version` | ☐ |
| 2.4 | nginx | 已安装并由 systemd 托管 | `nginx -v && systemctl is-active nginx` | ☐ |
| 2.5 | PG 时区 | UTC | `psql -p 5433 -U cmab_app -d cmab_mdm -c "SHOW timezone"` 返回 `UTC` | ☐ |
| 2.6 | PG 字符集 | UTF8；collation / ctype 与获批环境基线一致 | `psql -p 5433 -U cmab_app -d cmab_mdm -c "SELECT current_setting('server_encoding'), current_setting('lc_collate'), current_setting('lc_ctype')"` | ☐ |
| 2.7 | PG 扩展 | pgcrypto / pg_trgm / btree_gin / unaccent 已启用 | `psql -p 5433 -U cmab_app -d cmab_mdm -c "\dx"` 核对四个扩展均存在 | ☐ |
| 2.8 | Redis 持久化 | appendonly yes | `redis-cli -p 6379 CONFIG GET appendonly` | ☐ |

## 3. 应用基线（构建产物与运行时）

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 3.1 | 后端 venv Python | 3.12 | `backend/.venv/bin/python --version` | ☐ |
| 3.2 | Node 运行时（构建期）| 20 LTS | `node --version` | ☐ |
| 3.3 | pnpm | ≥ 9 | `pnpm --version` | ☐ |
| 3.4 | 后端关键依赖 | 对照 `backend/pyproject.toml` 锁定版本（fastapi/sqlalchemy/redis/slowapi/prometheus-fastapi-instrumentator/loguru/passlib/python-jose）| `backend/.venv/bin/pip list` 对比 | ☐ |
| 3.5 | 前端关键依赖 | 对照 `frontend/pnpm-lock.yaml` | `cd frontend && pnpm list --depth=0` | ☐ |
| 3.6 | 前端构建产物存在 | `frontend/dist/index.html` 为本次构建产物 | `ls -l /opt/cmab-mdm-platform/frontend/dist/index.html` | ⚠️ ☐ |
| 3.7 | 代码版本一致 | 工作树 = origin/main 目标 commit，无脏改 | `git -C /opt/cmab-mdm-platform rev-parse HEAD && git status -s` 无输出 | ⚠️ ☐ |

## 4. 配置文件完整性

> 后端以 `/opt/cmab-mdm-platform/backend` 为工作目录；`app.core.config.Settings` 从该目录的
> `.env` 读取配置。当前受管 systemd 单元没有 `EnvironmentFile=`。

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 4.1 | 后端配置存在 | `/opt/cmab-mdm-platform/backend/.env` 存在、非空、仅服务账号可读 | `sudo -u prometheus test -r /opt/cmab-mdm-platform/backend/.env` | ⚠️ ☐ |
| 4.2 | 必填项齐全 | `DATABASE_URL / DATABASE_URL_SYNC / SECRET_KEY / REDIS_URL / CORS_ORIGINS` 全部非 `_CHANGE_ME_` | 对 `backend/.env` 执行 `grep -E "_CHANGE_ME_"` 应**无输出** | ⚠️ ☐ |
| 4.3 | DB 连接指向本机 :5433 | `DATABASE_URL` 主机:端口 = `127.0.0.1:5433`、库 `cmab_mdm`、用户 `cmab_app` | 人工核对 `backend/.env` | ⚠️ ☐ |
| 4.4 | SECRET_KEY 强度 | ≥ 32 字符且非默认值 | `awk -F= '/^SECRET_KEY/{print length($2)}'` ≥ 32 | ⚠️ ☐ |
| 4.5 | **JWT RS256 启用** | `JWT_ALGORITHM=RS256` + 私/公钥路径文件存在且可读（见 RUNBOOK_JWT_RS256）| `grep JWT_ALGORITHM`（=RS256）；对 `JWT_PRIVATE_KEY_PATH`/`JWT_PUBLIC_KEY_PATH` `test -r` | ⚠️ ☐ |
| 4.6 | CORS_ORIGINS | 仅含实际访问的前端域名，不允许 `*` | 人工核对 | ☐ |
| 4.7 | HTTPS 前置（如启用）| 证书有效期 > 30 天 | `openssl x509 -in <本机证书路径> -enddate -noout` | ☐ |

## 5. 数据库初始化（集群 `mdm` :5433）

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 5.1 | 数据库已建 | `cmab_mdm` 存在 | `psql -p 5433 -U postgres -c "\l" \| grep cmab_mdm` | ☐ |
| 5.2 | 应用账号已建 | `cmab_app` 存在 + 可登录 | `psql -p 5433 -U postgres -c "\du cmab_app"` | ☐ |
| 5.3 | 审计审查账号 | `cmab_audit_reader` 存在 + 仅 audit schema 只读 | `psql -p 5433 -U postgres -c "\du cmab_audit_reader"` | ☐ |
| 5.4 | 全部 schema 已建 | auth / meta / audit / srs / prs / ars / mm / ref / eqp / tgt 共 10 个 | `psql -p 5433 -U cmab_app -d cmab_mdm -c "\dn"` 核对（另含 public）| ☐ |
| 5.5 | alembic head | `0062_eqp_total_weight` | `cd backend && .venv/bin/alembic current` | ⚠️ ☐ |
| 5.6 | 基线权限与角色 | 基线 seed + 定向迁移产生的权限、系统角色和配置均存在；不要以历史固定行数代替名称核对 | 见 §9 执行命令 5.6 | ☐ |
| 5.7 | code_sequence | substance / project / asset / material / equipment / target 取号配置就绪 | `psql -p 5433 -c "SELECT sequence_name FROM meta.code_sequence ORDER BY 1"` | ☐ |
| 5.8 | 全部 audit trigger 在位 | 迁移定义的业务审计触发器逐项存在，不以历史固定数量判断 | 用 §9 的 5.8 查询导出 schema / table / trigger 清单，与当前 migration 核对 | ⚠️ ☐ |

## 6. 服务启动与健康检查

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 6.1 | 后端服务 active | `cmab-backend.service` running + enabled | `systemctl status cmab-backend` / `systemctl is-enabled cmab-backend` | ⚠️ ☐ |
| 6.2 | 后端健康检查 | 200 + `{"status":"healthy","version":"V1.3-draft"}` | `curl -s --noproxy '*' http://127.0.0.1:18000/health` | ⚠️ ☐ |
| 6.3 | 前端 nginx 伺服 | 200，返回 SPA index | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:15173/` | ⚠️ ☐ |
| 6.4 | 门户 → 后端反代 | `/mdm/api` 经 cmab-hub nginx 通到 :18000 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5100/mdm/api/v1/health` = 200 | ⚠️ ☐ |
| 6.5 | API docs 关闭 | 生产 `ENABLE_API_DOCS=false`（或 production 默认值）→ 404 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18000/api/v1/docs` = 404 | ⚠️ ☐ |
| 6.6 | Redis 连接 | backend 启动日志含 Redis 就绪 | `journalctl -u cmab-backend \| grep -i redis` | ⚠️ ☐ |
| 6.7 | 日志格式 | 生产应 JSON 单行 | `journalctl -u cmab-backend -n 5 -o cat` 每行 JSON 解析成功 | ⚠️ ☐ |

## 7. 安全与合规检查

> **原型期形态：内网 HTTP 直连 nginx `:15173`，无 TLS 终止。** 故 HTTPS/TLS 相关项（7.2 / 7.3 / 7.5）标 **N/A**——待进入生产/GMP 准备阶段加 HTTPS 前置时再激活并重测。其余安全项（内部端口收敛、默认口令、/metrics 收敛、限流、审计触发器）原型期仍须执行。仓库内 `deploy/nginx/*` 是 docker-compose 网关，不代表本机。

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 7.1 | 内部端口不对公网 | :18000 / :5433 / :6379 仅本机/内网可达 | 从外网 `nc -vz <公网IP> 18000` 应失败 | ⚠️ ☐ |
| 7.2 | HTTPS 强跳 | 80 → 301 → 443 | 原型期内网 HTTP 直连，无 TLS | **N/A** |
| 7.3 | HSTS 头 | `Strict-Transport-Security` 存在 | 原型期内网 HTTP 直连，无 TLS | **N/A** |
| 7.4 | CSP 头 | `Content-Security-Policy` 含 `default-src 'self'`（如前端 nginx 已配置安全头）| `curl -I http://127.0.0.1:15173/` | ☐ |
| 7.5 | TLS 版本 | 仅 1.2 + 1.3 | 原型期内网 HTTP 直连，无 TLS | **N/A** |
| 7.6 | 默认账号密码已改 | admin 等默认口令已改 | 走 IT 安全部门 SOP | ⚠️ ☐ |
| 7.7 | /metrics 不对公网 | 公网拒绝（nginx 限内网 / 防火墙）| 从外网 `curl <前端入口>/metrics` 返回 403/404/超时 | ⚠️ ☐ |
| 7.8 | rate_limit 生效 | 11 次 login 出现 429 + Retry-After | 见 §9 执行命令 7.8 | ⚠️ ☐ |
| 7.9 | 审计触发器 | 生产只读核对触发器在位；写入功能在 UAT 用测试记录验证 | 见 §9 执行命令 7.9 | ⚠️ ☐ |

## 8. 备份与恢复

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 8.1 | BACKUP_DIR 存在且可写 | 目录存在 + 运行身份可写 | `BACKUP_DIR=${BACKUP_DIR:-/home/prometheus/cmc_backups/mdm}; sudo -u prometheus touch "$BACKUP_DIR/_iq_probe" && sudo -u prometheus rm "$BACKUP_DIR/_iq_probe"` | ☐ |
| 8.2 | 备份 cron / systemd timer | 已注册且 next-trigger 显示 | `systemctl list-timers cmab-mdm-backup.timer` 或 `crontab -l \| grep backup_db` | ⚠️ ☐ |
| 8.3 | 手工备份冒烟 | `scripts/backup_db.sh` 产出 .dump > 0 字节 | `sudo -u prometheus env BACKUP_MODE=native bash scripts/backup_db.sh`，再检查实际 `BACKUP_DIR` | ⚠️ ☐ |
| 8.4 | 备份保留窗口 | 30 天 | 确认 `RETENTION_DAYS` 已固化（见 RUNBOOK_BACKUP_RESTORE）| ☐ |
| 8.5 | 离线归档 | 备份已上传到对象存储 / 磁带 | 走运维 SOP | ☐ |
| 8.6 | 恢复演练 | 在隔离库 restore 成功 + alembic head 一致 | 见 RUNBOOK_BACKUP_RESTORE 恢复流程 | ☐ |

---

## 9. 关键执行命令（附录）

### 5.6 基线对象核对

```bash
psql -p 5433 -U cmab_app -d cmab_mdm -c "
  SELECT permission_code FROM auth.permission ORDER BY permission_code;
  SELECT role_code, is_system, deleted_at FROM auth.role
   WHERE deleted_at IS NULL
   ORDER BY role_code;
  SELECT config_key FROM meta.system_config
   WHERE config_key LIKE 'session.%' OR config_key='dept_admin.delegable_role_prefixes'
   ORDER BY config_key;"
```

角色清单应至少包含当前 baseline 的 14 个角色码：`SYS_ADMIN`、`SUBSTANCE_STEWARD`、
`PROJECT_MANAGER`、`CMC_RESEARCHER`、`QA_REVIEWER`、`READ_ONLY_USER`、
`CMC_WAREHOUSE_ADMIN`、`CMC_EQUIPMENT_ADMIN`、`DISPLAY_MODE`、`DEPT_ADMIN`、
`QV_ADMIN`、`QV_ENGINEER`、`QV_REVIEWER`、`QV_VIEWER`。

### 5.8 审计触发器清单

```bash
psql -p 5433 -U cmab_app -d cmab_mdm -c "
  SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname AS trigger_name
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE NOT t.tgisinternal AND t.tgname LIKE 'trg_%_audit'
   ORDER BY n.nspname, c.relname, t.tgname;"
```

### 7.8 限流冒烟

```bash
# 连发 11 次密码错误的 login（生产档 10/min/IP），第 11 次应 429
# <入口> = 实际对外入口（如 https://<域名> 或 http://127.0.0.1:15173）
for i in $(seq 1 11); do
  curl -s --noproxy '*' -o /dev/null -w "%{http_code} " \
    -X POST <入口>/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"non-exist","password":"x"}'
done
echo
# 期望输出最后一个为 429
```

### 7.9 审计触发器核对

```bash
# 生产环境：只读核对业务表上的审计触发器，不制造临时主数据
psql -p 5433 -U cmab_app -d cmab_mdm -c "
  SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname
    FROM pg_trigger t
    JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE NOT t.tgisinternal AND t.tgname LIKE 'trg_%_audit'
   ORDER BY 1,2,3;"

# UAT：通过界面创建并随后软删除一条明确标识为 OQ/IQ 测试的记录，
# 对比 audit.audit_log 与 audit.change_history；保存执行人、时间和记录编码。
```

---

## 10. 签字确认

| 角色 | 姓名 | 签字 | 日期 |
|---|---|---|---|
| 安装工程师 | | | |
| QA 复核 | | | |
| CSV 验证工程师 | | | |

**结论**：☐ 全部 PASS，进入 OQ；☐ 存在 FAIL 项，CAPA 单号 _______，整改后重测
