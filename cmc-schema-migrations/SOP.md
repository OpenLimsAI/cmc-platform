# CMC 数据平台 数据库标准操作流程（SOP）

> 适用范围：本仓库管理的 4 个库 + cmab_mdm 的所有**结构变更**（schema/表/列/索引/约束/视图/函数）。
> 不适用：纯数据 INSERT/UPDATE/DELETE、应用代码里的 SQL 查询。

---

## 0. 系统拓扑

```
                 ┌────────────────────────────────────┐
                 │  GitHub: qingcheng81/                │
                 │  cmc-schema-migrations (private)     │  ← 4 库的单一真理
                 └──────────────┬───────────────────────┘
                      git push  │  git pull
            ┌───────────────────┴────────────────────┐
            │                                         │
     ┌──────▼───────┐                         ┌───────▼────────┐
     │  Mac (dev)   │                         │ Linux VM(deploy)│
     │  Docker:     │                         │  原生三实例:     │
     │  rd_pg :5432 │  ──测试OK后 push──▶      │  rd_pg  :5432   │
     │  gmp_pg:5434 │                         │  mdm_pg :5433   │
     │  cmab :15432 │                         │  gmp_pg :5434   │
     └──────────────┘   ssh -p 13568 ...      └────────────────┘
```

**每个库的归属：**

| 库 | 实例 | 谁管 |
|---|---|---|
| cmc_rd / cmc_analytics / cmc_data_platform | rd_pg | **本仓库**（`dbmig <库>`）|
| cmc_gmp | gmp_pg | **本仓库**（`dbmig cmc_gmp`）|
| cmab_mdm | mdm_pg | **cmab-mdm-platform app**（`dbmig cmab_mdm` 转发，autogenerate）|

**铁律**：所有结构变更 → 写 Alembic migration → 落地测试 → push → 另一端 `dbmig <库> upgrade head`。
**永远不要**用 `psql -c "ALTER TABLE..."` 直接改库。

---

## 1. 日常：改一个库的标准流程

不管改哪个库，四步都一样（把 `<库>` 换成实际库名）。

> ⚠️ **动笔前先问一句：这张表有几个使用方？**（2026-08-04 LIMS 断流事故的教训）
> `meta.*`（etl_watermark / etl_run / etl_job …）、`dim.*`、`staging.*` 这类表往往被
> **多条管道共用**。改结构前必须把 `~/code` 下所有 `*-etl` / ingest / dashboard 仓库
> grep 一遍该表名，逐个确认兼容、一起改、一起验证：
> ```bash
> grep -rln "etl_watermark" ~/code/*/  --include="*.py" --include="*.sql" | grep -v .venv
> ```
> 2026-06-30 改 etl_watermark 只对齐了 lucullus、漏了 rd-lims-etl，后者静默挂了
> 一个月（cron 失败只进日志、无告警），看板 7 月数据几乎为空才被发现。

### 1.1 在 Mac 上写迁移

```bash
cd ~/code/cmc-schema-migrations
./dbmig <库> revision -m "add status_color to material"
# 生成: alembic/versions/<库>/<时间戳>_..._add_status_color_to_material.py
```

打开生成的 `.py`，写 `upgrade()` / `downgrade()`：

```python
def upgrade() -> None:
    op.add_column("material",
        sa.Column("status_color", sa.Text(), nullable=True),
        schema="material_mgmt")

def downgrade() -> None:
    op.drop_column("material", "status_color", schema="material_mgmt")
```

### 1.2 在 Mac 落地 + 验证

```bash
./dbmig <库> upgrade head --sql      # dry-run，仅打印 SQL
./dbmig <库> upgrade head            # 真正执行（落到 Mac docker）
./dbmig <库> current                 # 应看到新 head
# 进库看效果（Mac docker）：
docker exec -it rd_pg psql -U postgres -d <库> -c "\d material_mgmt.material"
```

### 1.3 跑应用验证

启动相关 app（cmc-inventory / dashboard / ETL …），确认新结构工作正常。

### 1.4 push

```bash
git add alembic/versions/<库>/ alembic/baselines/   # 若引用了 baseline/asset 也一并 add
git commit -m "feat(<库>): add status_color to material"
git push
```

### 1.5 Linux 同步

```bash
ssh -p 13568 prometheus@172.19.0.105
cd /opt/cmc-schema-migrations
git pull
./dbmig <库> upgrade head --sql       # 先 dry-run 看一眼
./dbmig <库> upgrade head             # 执行
./dbmig <库> current                  # 验证
```

> Linux 通过 TCP（127.0.0.1 + .env 里的 postgres 密码）连库，**无需 sudo**。
> cmab_mdm 的迁移在 `cmab-mdm-platform` repo 里写/push，Linux 上 `dbmig cmab_mdm upgrade head` 落地。

---

## 2. 漂移体检（兜底，建议每月一次）

万一有人绕过 Alembic 直接改了某库，靠列级指纹对比发现。

```bash
# 对某库，导出两端 information_schema.columns 指纹并 diff：
QRY="SELECT c.table_schema||'.'||c.table_name||'|'||c.column_name||'|'||c.data_type||'|'||c.is_nullable \
  FROM information_schema.columns c JOIN information_schema.tables t \
  ON t.table_schema=c.table_schema AND t.table_name=c.table_name AND t.table_type='BASE TABLE' \
  WHERE c.table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1"

# Mac:   docker exec rd_pg  psql -U postgres -d <库> -tAc "$QRY" | sort > /tmp/mac.txt
# Linux: psql -h127.0.0.1 -p <端口> -U postgres -d <库> -tAc "$QRY" | sort > /tmp/lin.txt
# diff /tmp/mac.txt /tmp/lin.txt   → 期望无差异
```

`tools/` 下还有更全的盘点/对比脚本（含视图/函数/索引），半年一次深度体检用。

---

## 3. 应急：发现漂移怎么办

| 情况 | 处理 |
|---|---|
| 漂出来的是还没写迁移的合法变更 | 在 Mac 上**追写 migration**（见 §5），`dbmig <库> upgrade head` 落 Mac，push，Linux 拉 |
| 临时调试遗留物 | 在那端**手动 DROP**，必要时补进迁移 |
| 两边都漂且方向不一致 | 先用列级对比定位，手动对齐后**重做该库 baseline**（pg_dump → 新 baseline → 两端 stamp --purge）|

**千万别做：**
- 不要 `git reset` 删迁移文件
- 不要用 `dbmig <库> stamp <old>` 把版本号往回退
- 不要手删 `alembic_version` 表

---

## 4. 新机器 / 新库 bootstrap

**新机器**（见 README「bootstrap」）：`git clone` → `uv venv` + 装依赖 → `cp .env.example .env` 填密码 → `chmod 600 .env`（明文库密码，仅本人可读写）→ `./dbmig list`。

**全新空库从 0 建到最新：**
```bash
createdb <库>                         # 或 docker exec ... createdb
./dbmig <库> upgrade head             # baseline 能从空库一把建全
```

---

## 5. 反向：把手动改的 schema 追录进 Alembic

如果某库已经被手动改了，要补录：

```bash
./dbmig <库> revision -m "describe the manual change"
# 在 upgrade() 写与已发生变更等价的 op.* 调用
# 已改过的那端：./dbmig <库> stamp head     （只打标，不重跑）
# 没改过的那端：./dbmig <库> upgrade head    （真正执行追上）
```

> 2026-06-04 我们就是这么把 Mac 手工建的 `equipment_mgmt`（cmc_data_platform）和
> `eqp`（cmab_mdm）补齐到 Linux 的——后者走的是 cmab app 的 alembic `0040`。

---

## 6. 常用速查

```bash
./dbmig list                          # 所有库当前版本一览
./dbmig <库> current                  # 某库当前版本
./dbmig <库> history --verbose        # 完整历史
./dbmig <库> upgrade head --sql       # 预览将执行的 SQL（不执行）
./dbmig <库> downgrade -1             # 回退一个版本（谨慎！）
./dbmig <库> show <rev>               # 看某 revision 细节
```

重做某库 baseline（结构演进很大、想清账时）：
```bash
# Mac 上：pg_dump --schema-only -d <库> > alembic/baselines/<库>.sql
# 替换 baseline 迁移 → 两端 ./dbmig <库> stamp <库>_baseline --purge
```

---

## 7. Mac / Linux 连接对照

写迁移文件两边完全一样，只是连库方式不同：

| 操作 | Mac (Docker) | Linux (原生) |
|---|---|---|
| 跑迁移 | `./dbmig <库> upgrade head` | `./dbmig <库> upgrade head`（同命令）|
| 进数据库 | `docker exec -it <实例> psql -U postgres -d <库>` | `psql -h127.0.0.1 -p <端口> -U postgres -d <库>` 或 `sudo -u postgres psql -p <端口> -d <库>` |
| 实例→端口 | rd_pg=5432, gmp_pg=5434, cmab=15432 | rd_pg=5432, gmp_pg=5434, mdm_pg=5433 |
| 连接凭据 | `.env` 共享（postgres / 统一密码 / 端口按库）；Mac↔Linux 通用 | 同左 |
