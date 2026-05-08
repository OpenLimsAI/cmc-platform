# Linux 服务器部署指南

> 本文档对应 README.md 第八节 "复用现有 PG 实例" 场景。
> 默认 `docker-compose.yml` 让 backend/frontend 都跑在 `network_mode: host`,
> backend 直接连宿主机 `127.0.0.1:5432`,因此**不需要**改 PG 的 `listen_addresses`、
> `pg_hba.conf`,也**不需要**重启 PG。

---

## 1. 在已有数据库 `cmc_data_platform` 里建 schema 与专用账号

> 一次性操作,需要超级用户身份。Debian/Ubuntu 装 PG 时 postgres 账号默认无密码,
> 走 Unix peer 认证(sudo)进 psql。

```bash
sudo -u postgres psql -d cmc_data_platform <<'EOF'
CREATE USER cmc_user WITH PASSWORD 'CmcMvp2026!Strong';
CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user;
EOF
```

执行后:
- 多了一个 schema `material_mgmt`,owner 是 `cmc_user`
- 多了一个账号 `cmc_user`,只能 CONNECT 这个库,只能在自己的 schema 内做 DDL/DML
- 原有 6 个 schema(`app_rd`、`raw_qc_lims` 等)、其他账号、密码、PG 配置 **零变化**

> 想用更强密码就把上面 `CmcMvp2026!Strong` 替换。改了之后 `.env` 里同步改。

---

## 2. 用 cmc_user 在 material_mgmt schema 内建表

```bash
cd /opt/cmc-inventory   # 或者 ~/cmc-inventory
PGPASSWORD='CmcMvp2026!Strong' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -f sql/init.sql
```

执行后会创建 7 张表 + 索引 + 触发器 + 单位/位置字典初始数据,
全部位于 `material_mgmt.*` 之下。重复执行也安全(`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`)。

验证:

```bash
PGPASSWORD='CmcMvp2026!Strong' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -c "\dt material_mgmt.*"
```

应看到 7 张表。

---

## 3. 准备 .env

```bash
cp .env.example .env
vim .env
```

至少改一行 —— 把 `DATABASE_URL` 里的密码替换成第 1 步实际用的:

```
DATABASE_URL=postgresql://cmc_user:你的真实密码@127.0.0.1:5432/cmc_data_platform
```

---

## 4. 启动

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

成功后访问:

- 前端: `http://<linux-server-ip>:8501`
- 后端 API: `http://<linux-server-ip>:8000/docs`

> 由于使用 `network_mode: host`,这两个端口直接绑到宿主机,无需 `-p` 映射。
> 防火墙(ufw/iptables/firewalld)按需放通 8501、8000 给内部用户。

---

## 5. 后续更新流程

```bash
cd /opt/cmc-inventory
git pull
docker compose up -d --build      # 重建镜像、滚动重启
docker compose logs -f backend
```

如有 SQL 增量(MVP 阶段表结构稳定),手工跑相应 migration。

---

## 6. 卸载(清理干净)

```bash
# 1. 停容器
docker compose down --rmi local

# 2. 删 schema 和账号
sudo -u postgres psql -d cmc_data_platform <<'EOF'
DROP SCHEMA material_mgmt CASCADE;
REVOKE CONNECT ON DATABASE cmc_data_platform FROM cmc_user;
DROP USER cmc_user;
EOF

# 3. 删代码(可选)
rm -rf /opt/cmc-inventory
```

之后宿主机 PG 完全恢复原状。

---

## 7. 常见问题

**Q: backend 启动报 `connection to server at "127.0.0.1", port 5432 failed`**
A: 在 host network 模式下应能直连。检查:
- `ss -ltnp | grep 5432`,PG 是否真的在监听 127.0.0.1:5432
- `.env` 里 DATABASE_URL 的密码是否与 cmc_user 的密码一致

**Q: backend 报 `permission denied for schema material_mgmt`**
A: 第 1 步的 `AUTHORIZATION cmc_user` 没生效,或第 2 步用错账号(用 postgres 跑 init.sql 会让表归 postgres 所有,cmc_user 反而读不到)。重新走第 2 步。

**Q: 端口被占用 / 8501/8000 已被别的服务占用**
A: 在 `docker-compose.yml` 里把 `network_mode: host` 改回 bridge + ports 映射到其他端口,或者停掉占用进程。

**Q: 想换成在容器里跑 PG**
A: 用备选 compose:`docker compose -f docker-compose.with-pg.yml up -d --build`(连同 PG 一起起一个容器)。
