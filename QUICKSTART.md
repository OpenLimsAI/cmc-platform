# 快速启动指南

> 5 分钟从零跑起 CMAB MDM Portal

## 前置要求

- ✅ Docker Desktop（Mac/Windows）或 Docker Engine + Compose v2（Linux）
- ✅ Git
- ✅ 至少 2GB 可用内存
- ✅ 端口可用：5173（前端）、8000（后端）、5432（数据库）、6379（Redis）

## 五步启动

### 1. 复制环境变量

```bash
cp .env.example .env
```

⚠️ 开发环境可直接使用默认值。生产环境必须修改 `SECRET_KEY` 和数据库密码。

### 2. 启动服务

```bash
make up
```

或者：

```bash
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

首次启动会构建镜像，约 3-5 分钟。

### 3. 等待健康检查通过

```bash
docker compose -f deploy/docker-compose.dev.yml ps
```

确认所有服务状态为 `running` 或 `healthy`。

### 4. 应用数据库迁移 + 加载种子数据

```bash
make migrate
make seed
```

### 5. 访问

| 入口 | URL | 默认账号 |
|------|-----|---------|
| 前端 | http://localhost:5173 | qingcheng / __REDACTED_SEED_PASSWORD_2__ |
| API 文档 | http://localhost:8000/api/v1/docs | - |
| 健康检查 | http://localhost:8000/health | - |

---

## 你应该看到

### 1. 登录页

蓝色渐变背景 + 居中卡片，输入 `qingcheng` / `__REDACTED_SEED_PASSWORD_2__` 登录。

### 2. 仪表盘

- 顶部欢迎语 + 当前日期
- 4 个统计卡片：物质 / 项目 / 资产 / 物料
- 物质卡片显示数字 4（来自种子数据）

### 3. 物质列表（点击侧边栏"物质"）

- 4 行示例数据：
  - SUB-0000001 单抗 CMAB-101 Anti-HER2 mAb (biosimilar)
  - SUB-0000002 单抗 CMAB-203 Anti-PD-L1 mAb 🔒 受限
  - SUB-0000003 双抗 CMAB-301 Bispecific HER2 x CD3
  - SUB-0000004 ADC CMAB-401 HER2-ADC (DXd)
- 状态彩色 Tag、类型 Tag、保密图标

### 4. 物质详情（点击任一编码）

- 顶部标题 + 状态 + 编码 + 类型
- 6 个 Tab：基本信息 / 结构与序列 / 标识符 / 关联 / 状态历史 / 审计
- 基本信息 Tab：分组展示所有字段
- 结构与序列 Tab：展示重链/轻链序列（仅 mAb 等蛋白类型）
- 标识符 Tab：展示 INN / CAS / PROJECT_CODE 等

---

## 常见问题

### Q1：端口冲突

如果 5432、6379、5173、8000 被占用，编辑 `deploy/docker-compose.dev.yml` 改 `ports` 映射。

### Q2：迁移失败

```bash
make logs-be          # 查看后端日志
make shell-be         # 进入容器排查
alembic current       # 检查当前迁移状态
```

### Q3：种子数据失败

通常是迁移未应用。先确认 `alembic upgrade head` 成功。

### Q4：前端页面空白

```bash
make logs-fe          # 检查前端日志
```

通常是依赖未装好，进入容器执行 `pnpm install` 再重启。

### Q5：登录失败"用户名或密码错误"

确认已执行 `make seed`。可在容器内手动测试：

```bash
docker compose -f deploy/docker-compose.dev.yml exec postgres \
    psql -U cmab_app -d cmab_mdm -c "SELECT username FROM auth.user"
```

### Q6：完全重置

```bash
make reset-db
```

---

## 开发模式（用 IDE 调试）

后端：

```bash
docker compose -f deploy/docker-compose.dev.yml up -d postgres redis
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
pnpm install
pnpm dev
```

修改代码自动热重载。
