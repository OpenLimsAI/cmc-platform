# Linux 服务器部署指南(复用宿主机 PG)

> 本文档针对 README.md 第八节的"复用本机已有 PG16"场景,补充具体步骤。
> 默认 `docker-compose.yml` 只跑 backend + frontend,PG 走宿主机。

---

## 1. 在宿主机 PG 上准备数据库与账号

以 `postgres` 超级用户登录:

```bash
sudo -u postgres psql
```

执行:

```sql
-- 创建专用账号(密码请与 .env 中保持一致)
CREATE USER cmc_user WITH PASSWORD 'change_me';

-- 创建专用数据库
CREATE DATABASE cmc_inventory OWNER cmc_user;

-- 退出
\q
```

---

## 2. 在新库中执行 init.sql

```bash
# 假设代码已 git pull 到 /opt/cmc-inventory
cd /opt/cmc-inventory

# 用 cmc_user 执行,所有对象归属正确
PGPASSWORD=change_me psql -h 127.0.0.1 -U cmc_user -d cmc_inventory -f sql/init.sql
```

执行后该库会有 `material_mgmt` schema 和 7 张表。

---

## 3. 让宿主机 PG 接受 Docker 容器的连接

容器走 `host.docker.internal`(在 docker-compose.yml 通过 `extra_hosts: host-gateway` 注入)
访问宿主机的 5432 端口。默认情况下 PG 只监听 localhost,需要放开。

### 3.1 修改 `postgresql.conf`

定位文件(Ubuntu/Debian 通常在 `/etc/postgresql/16/main/postgresql.conf`):

```bash
sudo find /etc -name postgresql.conf
sudo vim /etc/postgresql/16/main/postgresql.conf
```

把:

```
#listen_addresses = 'localhost'
```

改为(只监听 docker 网段更安全,这里给两种方案):

```
# 方案 A:监听全部接口(简单,但要确保防火墙没把 5432 暴露到外网)
listen_addresses = '*'
```

或

```
# 方案 B:只监听 docker0 桥接网段
# 需要先 ip addr show docker0 看到 172.17.0.1/16
listen_addresses = 'localhost,172.17.0.1'
```

### 3.2 修改 `pg_hba.conf`

```bash
sudo vim /etc/postgresql/16/main/pg_hba.conf
```

在文件末尾加一行(允许 docker 默认 bridge 网段的 cmc_user 通过密码连接 cmc_inventory):

```
# CMC 物料管理系统 — 允许 docker 容器连接
host    cmc_inventory   cmc_user   172.16.0.0/12   scram-sha-256
```

> 172.16.0.0/12 覆盖 Docker 默认 bridge(172.17.x.x)和大多数自定义网络。
> 若你用 `host network` 或自定义子网,按实际网段调整。

### 3.3 重启 PG

```bash
sudo systemctl restart postgresql
```

### 3.4 验证

```bash
# 从一个临时容器尝试连接宿主机 PG
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  postgres:16 psql -h host.docker.internal -U cmc_user -d cmc_inventory -c '\dn'
```

应能看到 `material_mgmt` schema。

---

## 4. 准备 .env 与防火墙

```bash
cd /opt/cmc-inventory
cp .env.example .env
vim .env   # 修改 DATABASE_URL 中的密码
```

`DATABASE_URL` 形如:

```
DATABASE_URL=postgresql://cmc_user:真实密码@host.docker.internal:5432/cmc_inventory
```

防火墙:开放 8501(前端)给内部用户访问。8000(后端)按需:

```bash
sudo ufw allow 8501/tcp
# 后端可选(若要直接访问 /docs)
sudo ufw allow 8000/tcp
```

---

## 5. 启动

```bash
cd /opt/cmc-inventory
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

成功后访问:

- 前端: `http://<linux-server-ip>:8501`
- 后端 API 文档: `http://<linux-server-ip>:8000/docs`

---

## 6. 后续更新流程

```bash
cd /opt/cmc-inventory
git pull
docker compose up -d --build      # 重新构建镜像并滚动更新
docker compose logs -f backend    # 观察启动日志
```

如果有新的 SQL 迁移(MVP 阶段表结构稳定,基本不会有),手动在 PG 中执行对应脚本。

---

## 7. 常见问题

**Q: 容器报 `could not translate host name "host.docker.internal"`**
A: Docker 版本太低。需要 ≥ 20.10,且 `extra_hosts: ["host.docker.internal:host-gateway"]` 在 compose 中已配置。`docker --version` 检查。

**Q: 容器能解析 host,但连接被拒(connection refused / no pg_hba.conf entry)**
A: 第 3 步未生效。检查:
- `sudo systemctl status postgresql` 是否重启
- `ss -ltnp | grep 5432` 是否在 `*:5432` 或 docker 网关 IP 上监听
- `sudo tail /var/log/postgresql/postgresql-16-main.log` 看具体拒绝原因

**Q: 想换成在容器里跑 PG**
A: 用备选 compose:`docker compose -f docker-compose.with-pg.yml up -d --build`。

**Q: 时区不对**
A: 容器已设 `TZ=Asia/Shanghai`,但 PG 的 timezone 由宿主机决定。可在 `postgresql.conf` 设 `timezone = 'Asia/Shanghai'`。
