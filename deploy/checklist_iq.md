# CMAB MDM Portal IQ 安装确认清单（P4.D-1）

| 项目 | 内容 |
|---|---|
| 文档编号 | IQ-MDM-001 |
| 版本 | V1.0 |
| 适用 | UAT / 生产首次部署 + 升级部署 |
| 合规 | GAMP 5 Cat 4 / 21 CFR Part 11 §11.10(b) 系统验证 / EU Annex 11 §4 |
| 执行人 | IT 安装工程师 |
| 复核人 | QA / CSV 验证工程师 |

---

## 0. 执行说明

- 本清单每一行都必须填写 **执行结果**（PASS/FAIL/N/A） + **执行人签名** + **日期**
- 任何 FAIL 项必须有偏差说明（CAPA 单号或同等记录），整改后重测
- 完整执行记录（含本表 + 截图 + 命令输出）归档到 GxP 文档管理系统，保留 ≥ 7 年
- 每次升级部署只需重跑变化项（标 ⚠️ 的必跑）

---

## 1. 操作系统与运行时基线

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 1.1 | 主机 OS | Linux x86_64（Ubuntu 22.04 LTS 或 RHEL 8+） | `uname -a` | ☐ |
| 1.2 | 主机 OS 时区 | UTC | `timedatectl status` | ☐ |
| 1.3 | Docker Engine | ≥ 24.0 | `docker --version` | ☐ |
| 1.4 | Docker Compose | ≥ 2.20 | `docker compose version` | ☐ |
| 1.5 | 磁盘空间 | 数据盘 ≥ 100 GB 可用 | `df -h /var/lib/docker /var/lib/cmab-mdm` | ☐ |
| 1.6 | 容器网络 MTU | ≥ 1450（避免分片）| `docker network inspect bridge` | ☐ |
| 1.7 | 主机防火墙 | 仅放行 80/443 入站，其它内网访问从 nginx 出站 | `iptables -L -n` 或 firewall-cmd | ☐ |

## 2. 中间件版本（容器镜像）

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 2.1 | PostgreSQL 镜像 | `postgres:16-alpine` | `docker compose images postgres` | ☐ |
| 2.2 | Redis 镜像 | `redis:7-alpine` | `docker compose images redis` | ☐ |
| 2.3 | Nginx 镜像（gateway）| `nginx:1.25-alpine` | `docker compose images gateway` | ☐ |
| 2.4 | PG 时区 | UTC（数据库级 + 容器级）| `docker exec cmab-mdm-postgres psql -c "SHOW timezone"` 返回 `UTC` | ☐ |
| 2.5 | PG 字符集 | UTF8 / en_US.utf8 | `psql -c "SHOW server_encoding, lc_collate, lc_ctype"` | ☐ |
| 2.6 | PG 扩展 | pgcrypto / pg_trgm / btree_gin / unaccent 已启用 | `psql -c "\dx"` 4 行齐 | ☐ |
| 2.7 | Redis 持久化 | appendonly yes | `docker exec cmab-mdm-redis redis-cli CONFIG GET appendonly` | ☐ |

## 3. 应用基线（构建产物）

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 3.1 | Python 运行时 | 3.12 | `docker exec cmab-mdm-backend python --version` | ☐ |
| 3.2 | Node 运行时（构建期）| 20 LTS | 构建日志中确认 base image `node:20-alpine` | ☐ |
| 3.3 | pnpm | 9.0.0 | 构建日志确认 `corepack prepare pnpm@9.0.0` | ☐ |
| 3.4 | 后端关键依赖 | 对照 `backend/pyproject.toml` 锁定版本（fastapi/sqlalchemy/redis/slowapi/prometheus-fastapi-instrumentator/loguru/passlib/python-jose）| `docker exec cmab-mdm-backend pip list` 对比 | ☐ |
| 3.5 | 前端关键依赖 | 对照 `frontend/pnpm-lock.yaml` | `docker exec cmab-mdm-frontend pnpm list --depth=0` | ☐ |
| 3.6 | 镜像 tag 不可变 | 部署镜像必须带版本 tag，**不允许 `:latest`** | `docker compose config \| grep image` | ⚠️ ☐ |

## 4. 配置文件完整性

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 4.1 | `.env.prod` 存在 | 文件存在且非空 | `test -s /etc/cmab-mdm/.env.prod` | ⚠️ ☐ |
| 4.2 | `.env.prod` 必填项齐全 | `POSTGRES_DB / POSTGRES_DBA_USER / POSTGRES_DBA_PASSWORD / POSTGRES_USER / POSTGRES_PASSWORD / SECRET_KEY / CORS_ORIGINS` 全部非 `_CHANGE_ME_` | `grep -E "_CHANGE_ME_" /etc/cmab-mdm/.env.prod` 应**无输出** | ⚠️ ☐ |
| 4.3 | SECRET_KEY 强度 | ≥ 32 字符且非默认值 | `grep SECRET_KEY /etc/cmab-mdm/.env.prod \| awk -F= '{print length($2)}'` ≥ 32 | ⚠️ ☐ |
| 4.4 | CORS_ORIGINS | 仅含实际访问的 HTTPS 前端域名，不允许 `*` 或 `http://` | 人工核对 | ☐ |
| 4.5 | TLS 证书 | `deploy/nginx/certs/{fullchain.pem,privkey.pem}` 存在 + 有效期 > 30 天 | `openssl x509 -in fullchain.pem -enddate -noout` | ⚠️ ☐ |
| 4.6 | docker-compose.prod.yml 校验 | `docker compose config` 无错 | `docker compose -f deploy/docker-compose.prod.yml --env-file /etc/cmab-mdm/.env.prod config -q` | ☐ |

## 5. 数据库初始化

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 5.1 | 数据库已建 | `cmab_mdm` 存在 | `psql -U postgres -c "\l" \| grep cmab_mdm` | ☐ |
| 5.2 | 应用账号已建 | `cmab_app` 存在 + 可登录 | `psql -U postgres -c "\du cmab_app"` | ☐ |
| 5.3 | 审计审查账号 | `cmab_audit_reader` 存在 + 仅 audit schema 只读 | `psql -U postgres -c "\du cmab_audit_reader"` | ☐ |
| 5.4 | 全部 schema 已建 | auth / meta / audit / srs / prs / ars / mm / ref 8 个（init.sql 建）+ eqp（migration 0040 建）共 9 个 schema | `psql -U cmab_app -d cmab_mdm -c "\dn"` 数行 = 9（另含 public）| ☐ |
| 5.5 | alembic head | `0044_eqp_identifiers` | `docker exec cmab-mdm-backend alembic current` | ⚠️ ☐ |
| 5.6 | 关键表行数 | auth.permission ≥ 23 / auth.role ≥ 8 / auth.user ≥ 5（含 admin）/ meta.lookup_value ≥ 30 / meta.system_config ≥ 5 | 见执行命令章节 | ☐ |
| 5.7 | code_sequence | 5 域年度序列就绪（substance / project / asset / material / equipment）| `psql -c "SELECT sequence_name FROM meta.code_sequence"` | ☐ |
| 5.8 | 全部 audit trigger 在位 | 业务表均挂 `trg_*_audit` | `psql -c "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'trg_%_audit'"` ≥ 12 | ⚠️ ☐ |

## 6. 服务启动与健康检查

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 6.1 | 所有容器 healthy | 5 个服务全 healthy | `docker compose ps` 全部 `(healthy)` | ⚠️ ☐ |
| 6.2 | 后端健康检查 | 200 + `{"status":"healthy"}` | `curl https://<域名>/health` | ⚠️ ☐ |
| 6.3 | API docs 关闭 | 生产 `APP_DEBUG=false` 应返回 404 | `curl -o /dev/null -w "%{http_code}" https://<域名>/api/v1/docs` = 404 | ⚠️ ☐ |
| 6.4 | Prometheus 指标 | 200 + Prometheus 格式 | `curl -H "Host: <域名>" http://<内网 IP>/metrics \| head -5` | ☐ |
| 6.5 | Redis 连接 | backend lifespan 日志含 `✓ Redis 连接已就绪` | `docker logs cmab-mdm-backend \| grep Redis` | ⚠️ ☐ |
| 6.6 | 日志格式 | 生产应 JSON 单行 | `docker logs cmab-mdm-backend --tail 5` 每行 JSON 解析成功 | ⚠️ ☐ |

## 7. 安全与合规检查

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 7.1 | HTTPS 强跳 | 80 → 301 → 443 | `curl -I http://<域名>` 应见 `Location: https://...` | ⚠️ ☐ |
| 7.2 | HSTS 头 | `Strict-Transport-Security: max-age=63072000` | `curl -I https://<域名>` | ⚠️ ☐ |
| 7.3 | CSP 头 | `Content-Security-Policy` 含 `default-src 'self'` | `curl -I https://<域名>` | ☐ |
| 7.4 | TLS 版本 | 仅 1.2 + 1.3，禁 1.0/1.1 | `nmap --script ssl-enum-ciphers -p 443 <域名>` | ⚠️ ☐ |
| 7.5 | 弱密码字典扫描 | admin 等默认账号密码已改 | 走 IT 安全部门 SOP | ⚠️ ☐ |
| 7.6 | /metrics 公网访问 | 应被 nginx 拒绝 | `curl https://<域名>/metrics` 返回 403/404 | ⚠️ ☐ |
| 7.7 | rate_limit 生效 | 11 次 login 出现 429 + Retry-After | 见执行命令章节 7.7 | ⚠️ ☐ |
| 7.8 | 审计触发器写入 | 任意 POST 后 audit.audit_log 多一行 | 见执行命令章节 7.8 | ⚠️ ☐ |

## 8. 备份与恢复

| # | 检查项 | 期望值 | 执行命令 | 结果 |
|---|---|---|---|---|
| 8.1 | BACKUP_DIR 存在且可写 | 容器可挂载 + 容器 user 写入权限 | `docker exec cmab-mdm-postgres touch /backups/_iq_probe && rm /backups/_iq_probe` | ☐ |
| 8.2 | 备份 cron / systemd timer | 已注册且 next-trigger 显示 | `systemctl list-timers cmab-mdm-backup.timer` 或 `crontab -l \| grep backup` | ⚠️ ☐ |
| 8.3 | 手工备份冒烟 | `make backup` 或 `scripts/backup_db.sh` 产出 .dump > 0 字节 | `bash scripts/backup_db.sh && ls -lh ${BACKUP_DIR}` | ⚠️ ☐ |
| 8.4 | 备份保留窗口 | 30 天 | 配置 `RETENTION_DAYS` 已固化 | ☐ |
| 8.5 | 离线归档 | 备份已上传到对象存储 / 磁带 | 走运维 SOP | ☐ |

---

## 9. 关键执行命令（附录）

### 5.6 关键表行数

```bash
docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -c "
  SELECT 'auth.permission' AS tbl, count(*) FROM auth.permission
  UNION ALL SELECT 'auth.role',         count(*) FROM auth.role
  UNION ALL SELECT 'auth.user',         count(*) FROM auth.user
  UNION ALL SELECT 'meta.lookup_value', count(*) FROM meta.lookup_value
  UNION ALL SELECT 'meta.system_config',count(*) FROM meta.system_config
  ;"
```

### 7.7 限流冒烟

```bash
# 连发 11 次密码错误的 login（生产档 10/min/IP），第 11 次应 429
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code} " \
    -X POST https://<域名>/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"non-exist","password":"x"}'
done
echo
# 期望输出最后一个为 429
```

### 7.8 审计触发器写入

```bash
# 先记一下审计行数
BEFORE=$(docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -At -c \
  "SELECT count(*) FROM audit.audit_log")

# 用 admin POST 一个临时物质
TOK=$(curl -s -X POST https://<域名>/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<改后密码>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["access_token"])')
curl -s -X POST https://<域名>/api/v1/substances \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"substance_type":"mab","internal_code":"IQ-PROBE","preferred_name":"IQ probe"}' \
  > /dev/null

# 再记审计行数
AFTER=$(docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -At -c \
  "SELECT count(*) FROM audit.audit_log")
echo "before=$BEFORE after=$AFTER（期望 after > before）"
```

---

## 10. 签字确认

| 角色 | 姓名 | 签字 | 日期 |
|---|---|---|---|
| 安装工程师 | | | |
| QA 复核 | | | |
| CSV 验证工程师 | | | |

**结论**：☐ 全部 PASS，进入 OQ；☐ 存在 FAIL 项，CAPA 单号 _______，整改后重测
