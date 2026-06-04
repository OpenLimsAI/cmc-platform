# cmc_data_platform 数据库标准操作流程（SOP）

> 适用范围：`cmc_data_platform` 数据库的所有结构（schema/表/列/索引/约束/视图/函数）变更。
> 不适用：纯数据 INSERT/UPDATE/DELETE、应用代码里的 SQL 查询。

---

## 0. 系统拓扑

```
                         ┌─────────────────────────┐
                         │ cmc-schema-migrations   │
                         │  (git 远端，单一真理)    │
                         └──────────┬──────────────┘
                                    │  git push / pull
                ┌───────────────────┼────────────────────┐
                │                   │                    │
        ┌───────▼──────┐   ┌────────▼─────────┐  ┌──────▼────────┐
        │  Mac (dev)   │   │  Linux VM (deploy)│  │ Windows (备份) │
        │  Docker PG16 │   │  原生 PG16        │  │ 不直连数据库   │
        │  容器:        │   │  端口: 5432       │  │ 仅留工具脚本   │
        │  rd_pg :5432 │   │  ssh -p 13568     │  │                │
        │ (旧postgres16│   │                   │  │                │
        │  已删除)      │   │                   │  │                │
        └──────────────┘   └──────────────────┘  └────────────────┘
```

**铁律**：所有 `cmc_data_platform` 结构变更 → 写 Alembic migration → 落地 → push → 另一端 `alembic upgrade head`。
**永远不要**用 `psql -c "ALTER TABLE..."` 直接改库。

---

## 1. 日常：改一个 schema 的标准流程

### 1.1 在 Mac 上写迁移

```bash
cd ~/cmc-schema-migrations
source .venv/bin/activate

# 起一个空白迁移，文件名按你做的事命名
alembic revision -m "add status_color column to dim_method"
# 生成: alembic/versions/004_add_status_color_column_to_dim_method.py
```

打开生成的 `.py`，写 `upgrade()` 和 `downgrade()`：

```python
def upgrade() -> None:
    op.add_column(
        "dim_method",
        sa.Column("status_color", sa.Text(), nullable=True),
        schema="meta",
    )

def downgrade() -> None:
    op.drop_column("dim_method", "status_color", schema="meta")
```

### 1.2 在 Mac 上落地 + 验证

```bash
# 看一下要跑什么
alembic upgrade head --sql                    # 仅打印 SQL，不执行（dry-run）

# 真正执行
alembic upgrade head

# 验证当前版本
alembic current                                # 应该看到 004 (head)

# 进库看看效果
docker exec -i rd_pg psql -U postgres -d cmc_data_platform -c "\d material_mgmt.material"
```

### 1.3 跑应用代码确认没踩坑

启动你的应用（tt-lims-platform / cmc-inventory / ...），验证新字段、新表确实工作正常。

### 1.4 push 到远端

```bash
cd ~/cmc-schema-migrations
git add alembic/versions/004_*.py             # 注意：如果有大段 DDL，也要 add assets/004/
git commit -m "add status_color to meta.dim_method"
git push
```

### 1.5 在 Linux 上同步

```powershell
# Windows PowerShell，SSH 进 Linux
ssh -p 13568 prometheus@172.19.0.105
```

在 Linux 上：

```bash
cd ~/cmc-schema-migrations
git pull
source .venv/bin/activate

# dry-run 看一眼
alembic upgrade head --sql

# 真正执行（需要写库权限，所以走 sudo -u postgres）
sudo -u postgres bash -c '
  cd /home/prometheus/cmc-schema-migrations
  ./.venv/bin/alembic upgrade head
'

# 验证
sudo -u postgres /home/prometheus/cmc-schema-migrations/.venv/bin/alembic current
sudo -u postgres psql -d cmc_data_platform -c "SELECT * FROM alembic_version;"
```

完成。两库结构一致。

---

## 2. 紧急体检：用对比脚本验证两库一致

这是兜底机制——万一有人绕过了 Alembic 直接改库，靠这一步发现。**建议每月一次**。

### 2.1 Mac 上跑盘点

```bash
cd ~                                           # 或脚本所在目录
source pg-inventory-venv/bin/activate

PGPASSWORD=YourStrongPassword_2026 python3 export_postgres_inventory.py \
  --host 127.0.0.1 --port 5432 --user postgres \
  --maintenance-db postgres \
  --outdir ./pg_inventory_mac_$(date +%Y-%m-%d)

# 直接送到 Linux（或 Windows，看你怎么集中）
scp -P 13568 -r ./pg_inventory_mac_$(date +%Y-%m-%d) prometheus@172.19.0.105:/tmp/
```

### 2.2 Linux 上跑盘点

```bash
cd ~/sql
source pg-inventory-venv/bin/activate

DAY=$(date +%Y-%m-%d)
OUT=/tmp/pg_inventory_linux_$DAY
sudo -u postgres /home/prometheus/sql/pg-inventory-venv/bin/python \
  /home/prometheus/sql/export_postgres_inventory.py \
  --host /var/run/postgresql --port 5432 --user postgres \
  --maintenance-db postgres \
  --outdir $OUT
```

### 2.3 拉回 Windows + 对比

```powershell
cd F:\Python\sql\

# 假设你已经把两份盘点放到 F:\Python\sql\ 下
python compare_pg_inventory.py `
  pg_inventory_mac_2026-XX-XX\inventory_full.json `
  pg_inventory_linux_2026-XX-XX\inventory_full.json `
  --database cmc_data_platform `
  --left-label mac --right-label linux `
  --out diff_mac_vs_linux_2026-XX-XX.md
```

**期望结果**：`总差异条目数：0`。
任何非 0 的差异 → 进入 §3 应急处理。

---

## 3. 应急：发现漂移怎么办

### 3.1 先搞清楚漂的是谁

看 diff 报告里的"只在 mac 有 / 只在 linux 有"，对照 git log：

```bash
git log alembic/versions/ --oneline | head -20
```

最后一次 commit 之后，谁多了东西、谁缺东西？

### 3.2 三种处理路径

| 情况 | 处理 |
|---|---|
| 漂出来的是 Alembic 还没写的合法变更 | 在 Mac 上**追写 migration**，`alembic upgrade head` 落到 Mac，push，Linux 拉 |
| 漂出来的是临时调试遗留物 | 在那一端**手动 DROP 掉**，并写进未来的 Alembic（也可不写） |
| 两边都 drift 且方向不一致 | 走 2026-05-13 那次的流程：手动对齐 + 补一个 baseline 迁移 |

### 3.3 千万别做

- **不要** `git reset` 删 migration 文件
- **不要** 用 `alembic stamp <old>` 把版本号回退（会让数据库认为没改过，下次 upgrade 就跑两遍）
- **不要** 删 `alembic_version` 表

---

## 4. 新加一台环境（比如开发新 VM）

```bash
# 在新机器上，假设已经装了 PostgreSQL 16
git clone <你的远端>/cmc-schema-migrations.git
cd cmc-schema-migrations

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配 .env（按这台机器的连接方式）
cp .env.example .env
# 编辑 .env 填 DATABASE_URL

# 把数据库 schema 从 0 建到当前 head
createdb cmc_data_platform                    # 如果还没建库
alembic upgrade head                          # 一气呵成跑完 001 → 003 → 现在
```

这就是 Alembic 最爽的地方：一行命令从空数据库建到最新结构。

---

## 5. 反向：从结构变更"逆向"出 Alembic 迁移

如果你（或别人）已经在某个库上手动改了 schema，要把它**追录**进 Alembic：

### 5.1 写一个新 migration

```bash
alembic revision -m "describe the manual change that was made"
```

### 5.2 在 upgrade() 里写**与已发生的变更等价**的 op.\* 调用

```python
def upgrade() -> None:
    op.add_column("foo", sa.Column("bar", sa.Text()), schema="meta")
```

### 5.3 在已变更过的数据库上 `alembic stamp head`

这样 alembic_version 知道"我们已经到这里了"，不会在这台库上重跑 SQL。

### 5.4 其他没改过的数据库上 `alembic upgrade head`

那些库会真正执行 SQL 把结构追上。

> 这正是 2026-05-13 我们处理 baseline 时走的路。看 `alembic/versions/003_align_dual_env_baseline.py` 的注释作为案例。

---

## 6. 一些常用速查

### 查当前版本
```bash
alembic current
```

### 查完整迁移历史
```bash
alembic history --verbose
```

### 看下一次 upgrade 会跑什么
```bash
alembic upgrade head --sql > preview.sql
```

### 强行回退一个版本（谨慎！）
```bash
alembic downgrade -1
```

### 看某个 revision 的细节
```bash
alembic show 003
```

---

## 7. Mac / Linux 命令对照表

写迁移文件本身两边一样，只是**连接和 sudo 不同**：

| 操作 | Mac (Docker) | Linux (原生) |
|---|---|---|
| 进数据库 | `docker exec -it rd_pg psql -U postgres -d cmc_data_platform` | `sudo -u postgres psql -d cmc_data_platform` |
| 跑 alembic | 普通 `alembic upgrade head`（venv 用户即可） | `sudo -u postgres ./.venv/bin/alembic upgrade head`（因为要写 alembic_version 表） |
| 灌 SQL 文件 | `docker exec -i rd_pg psql -U postgres -d cmc_data_platform < ./x.sql` | `sudo -u postgres psql -d cmc_data_platform -f /path/to/x.sql` |
| 导 SQL | `docker exec -e PGPASSWORD=YourStrongPassword_2026 rd_pg pg_dump ... > ./x.sql` | `sudo -u postgres pg_dump ... > /tmp/x.sql` |
| 看版本号 | `docker exec -i rd_pg psql -U postgres -d cmc_data_platform -c "SELECT * FROM alembic_version;"` | `sudo -u postgres psql -d cmc_data_platform -c "SELECT * FROM alembic_version;"` |
