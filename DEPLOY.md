# Linux 服务器部署指南(无 Docker 版)

> **架构选择**:不用 Docker 跑应用,直接 Python venv + systemd。
> 原因:数据库已在宿主机、镜像源被墙、调试更直接。
>
> 整体目录:`/opt/cmc-inventory`,运行身份 `prometheus`,数据库 `cmc_data_platform`。

---

## 0. 前置准备(只做一次)

服务器 OS 上需要:

```bash
# 1) Python 3.10+(Debian 12 / Ubuntu 22.04 默认是 3.11,直接装包就行)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# 2) 让 prometheus 用户可以写 /opt/cmc-inventory(若还没建):
sudo mkdir -p /opt/cmc-inventory
sudo chown prometheus:prometheus /opt/cmc-inventory
```

---

## 1. 数据库一次性初始化

> 在已有数据库 `cmc_data_platform` 内加 schema、新建专用账号。
> 不动其他 schema、不动其他账号、不动 PG 配置、不重启 PG。

```bash
sudo -u postgres psql -d cmc_data_platform <<'EOF'
CREATE USER cmc_user WITH PASSWORD '<your-password>';
CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user;
EOF
```

> 想换 cmc_user 密码,把上面与下面 `.env` 里两处一起改。

接着用 `cmc_user` 在 `material_mgmt` schema 内建表/索引/字典:

```bash
cd /opt/cmc-inventory
PGPASSWORD='<your-password>' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -f sql/init.sql
```

验证(应能看到 10 张表,owner 都是 cmc_user):

```bash
PGPASSWORD='<your-password>' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -c '\dt material_mgmt.*'
```

---

## 2. 拉代码

```bash
git clone git@github.com:qingcheng81/cmc-inventory.git /opt/cmc-inventory
# 或
git clone https://github.com/qingcheng81/cmc-inventory.git /opt/cmc-inventory
```

---

## 3. 准备 .env

```bash
cd /opt/cmc-inventory
cp .env.example .env
vim .env   # 修改 DATABASE_URL 中的密码,与第 1 步保持一致
```

`.env` 关键项:

```
BACKEND_PORT=8000
FRONTEND_PORT=8501
DATABASE_URL=postgresql://cmc_user:你的真实密码@127.0.0.1:5432/cmc_data_platform
API_BASE_URL=http://localhost:8000
ADMIN_INITIAL_PASSWORD=ChangeMeAtFirstLogin
```

> **格式严格** —— systemd 不允许加引号,KEY=VALUE 之间不能有空格。
> `API_BASE_URL` 的端口要和 `BACKEND_PORT` 保持一致。

---

## 4. 一键安装并启动

```bash
cd /opt/cmc-inventory
./install.sh
```

脚本做了什么:
1. `python3 -m venv backend/.venv` + `pip install -r backend/requirements.txt`
2. `python3 -m venv frontend/.venv` + `pip install -r frontend/requirements.txt`
3. 把 `systemd/*.service` 复制到 `/etc/systemd/system/`(需 sudo)
4. `systemctl daemon-reload` + `enable --now` 两个服务

成功后:

- 前端: `http://<服务器IP>:8501`
- 后端:只监听服务器本机 `127.0.0.1:8000`;看 Swagger `/docs` 需要 SSH 隧道,见第 6 节

---

## 5. 日常运维

| 操作 | 命令 |
|---|---|
| 看后端日志(实时) | `sudo journalctl -u cmc-backend -f` |
| 看前端日志 | `sudo journalctl -u cmc-frontend -f` |
| 重启后端 | `sudo systemctl restart cmc-backend` |
| 重启前后端(推荐) | `./restart.sh` |
| 重启前后端(旧方式) | `./install.sh restart` |
| 查状态 | `sudo systemctl status cmc-backend cmc-frontend` |
| 改代码后重启 | `cd /opt/cmc-inventory && git pull && ./restart.sh` |
| 改了 requirements.txt | `./install.sh deps && ./restart.sh` |
| 卸载(只删 unit/进程,不删数据) | `./install.sh uninstall` |

---

## 6. 防火墙

后端 uvicorn 只绑 `127.0.0.1`;虽然已有应用登录鉴权,仍不建议把 API 直接暴露给内网用户。只放通前端端口:

```bash
sudo ufw allow 8501/tcp comment 'cmc-inventory frontend'
# 不放通 8000:后端只允许同机 localhost 访问
```

需要从办公网看 Swagger `/docs` 时,用 SSH 隧道把后端临时映射出来:

```bash
# 在自己的笔记本上跑
ssh -L 18000:127.0.0.1:8000 prometheus@<服务器IP>
# 浏览器打开 http://localhost:18000/docs
```

---

## 7. 从旧版本升级到当前版本

> 当前服务器若已经按本文档跑过旧版本,按下面流程升级到当前版本。
> 不需要 down time(systemd restart 间隔约 1-2 秒)。

```bash
cd /opt/cmc-inventory

# 1) 拉新代码
git pull --ff-only

# 2) 跑幂等建表/迁移脚本
#    init.sql 大多为 IF NOT EXISTS,用于补齐基础表和字典
PGPASSWORD='<your-password>' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -f sql/init.sql

# 若你的服务器不是全新按当前 init.sql 建的库,还需要执行 v1.2 迁移脚本
PGPASSWORD='<your-password>' psql -h 127.0.0.1 -U cmc_user \
    -d cmc_data_platform -f sql/migrate_v1_2.sql

# 3) 确认 .env 里有 ADMIN_INITIAL_PASSWORD(首次启动后端会用它自动建 admin)
grep -q '^ADMIN_INITIAL_PASSWORD=' .env || \
    echo 'ADMIN_INITIAL_PASSWORD=ChangeMeAtFirstLogin' >> .env

# 4) 装/更新依赖 + 重装 systemd unit + 重启
./install.sh deps
./install.sh install
./restart.sh
```

启动后端日志会打印:`已创建初始 admin 账号(must_change_password=True)`。

**首次登录:** 浏览器开 `http://<server-ip>:8501` → 用户名 `admin`,密码 = 你设的 `ADMIN_INITIAL_PASSWORD` → 系统会强制让你改密码 → 改完后用新密码重新登录。

之后:

- 普通同事:在「用户管理」页给他们建 user 账号,告诉他们用户名 + 初始密码,他们自己改密
- `.env` 中的 `ADMIN_INITIAL_PASSWORD` 改完后**保留即可**(后续启动若 app_user 已有数据,这个变量不再生效)

⚠️ 升级后,**手填的"经办人"输入框消失了** —— 入库 / 出库 / 盘点 / 物料停用 等操作的"经办人"自动取登录用户名,所有写操作记 audit_log,可在「用户管理 → 操作日志」tab 中查询。

---

## 8. 彻底卸载(回到部署前的状态)

```bash
# 1) 停服务、删 systemd unit
cd /opt/cmc-inventory && ./install.sh uninstall

# 2) 删 schema 和账号
sudo -u postgres psql -d cmc_data_platform <<'EOF'
DROP SCHEMA material_mgmt CASCADE;
REVOKE CONNECT ON DATABASE cmc_data_platform FROM cmc_user;
DROP USER cmc_user;
EOF

# 3) 删代码 / venv
sudo rm -rf /opt/cmc-inventory
```

---

## 9. 常见问题

**Q: backend 起不来,journalctl 报 `password authentication failed`**
A: `.env` 中 `DATABASE_URL` 的密码与 cmc_user 的真实密码不一致。改 `.env` 后 `./restart.sh`。

**Q: backend 起来但报 `permission denied for schema material_mgmt`**
A: init.sql 是用 postgres 身份跑的,导致表归 postgres 所有。改用 cmc_user 跑一次:
```bash
PGPASSWORD='...' psql -h 127.0.0.1 -U cmc_user -d cmc_data_platform -f sql/init.sql
```

**Q: 前端打开但调用接口报错**
A: 检查 backend 是否在跑:`curl http://127.0.0.1:8000/health`。另外 `.env` 里 `API_BASE_URL` 应是 `http://localhost:8000` 或 `http://127.0.0.1:8000`(同机部署)。

**Q: 端口被占用**
A: `ss -ltnp | grep -E '8000|8501'` 查谁占着。通常只需要改 `.env` 中的 `BACKEND_PORT` / `FRONTEND_PORT`,并同步修改 `API_BASE_URL` 的端口,然后 `./restart.sh`。

**Q: 想加开机自启 / 取消自启**
A: install.sh 默认已 `enable`。
- 取消自启:`sudo systemctl disable cmc-backend cmc-frontend`
- 重新自启:`sudo systemctl enable cmc-backend cmc-frontend`
