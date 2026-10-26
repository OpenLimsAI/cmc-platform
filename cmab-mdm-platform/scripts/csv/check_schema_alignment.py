#!/usr/bin/env python3
"""schema 一致性 CI 门禁（P4.D-3）

对比：
  - 实际 DB：information_schema.columns（去掉 _at/audit/触发器维护字段后的字段集）
  - 设计基线：docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md 中所有 `CREATE TABLE schema.table (...)` 块

输出：
  - 每张表：[DB 多余] / [DB 缺失] / [字段名两边一致] 三段
  - 全局 exit code：0 = 全部对齐 / 1 = 存在偏离

设计取舍（务实优先）：
  - **仅对比字段名集合**（不对比类型 / nullable / 默认值 / CHECK / FK）
  - 设计上某些表（如 srs.substance_alias / prs.project_relationship / staging.substance_import_*）
    V1.1 列出但 Phase 4 尚未实施 → 通过 `EXPECTED_UNIMPLEMENTED` 白名单豁免
  - 实施侧补齐的字段（如 material_batch.deleted_by 等 V1.2 修订八登记的"实施侧合理加强"）→
    通过 `IMPLEMENTATION_ADDED` 白名单豁免

用法：
  python scripts/csv/check_schema_alignment.py        # 默认连容器 PG
  DATABASE_URL_SYNC=postgresql://... ./check_schema_alignment.py
  make check-schema                                   # 推荐入口
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg2  # noqa: E402 — pip install 在 backend 容器内

ROOT = Path(__file__).resolve().parent.parent.parent
# 默认从 repo docs/ 取；CI 容器内可通过 DM_MD_OVERRIDE 覆盖路径
DM_MD = Path(
    os.environ.get("DM_MD_OVERRIDE")
    or (ROOT / "docs" / "CMAB_MDM_Portal_数据模型设计文档_V1_1.md")
)

# ============== 设计 v.s. 实施差异豁免清单（V1.2 偏离说明已登记）==============

# V1.1 列了但 Phase 4 尚未实施的表（推迟到 Phase 5+）
EXPECTED_UNIMPLEMENTED: set[str] = {
    "auth.password_history",          # Phase 5 密码历史（接 21 CFR 11 §11.300）
    "srs.substance_alias",            # 曾用名表，Phase 5
    "prs.project_relationship",       # 项目上下级关系，B 决议 Phase 5（P8）
    "staging.substance_import_2026",  # 数据导入暂存（V1.1 §14 列示例），Phase 5
    "staging.substance_import_batch",
    "staging.substance_import_row",
    "staging.substance_import_error",
}

# Phase 1-4 实施侧补齐的字段（V1.2 偏离说明各章节登记）
# 字典 key = "schema.table"，value = 实际多出的字段（whitelist）
IMPLEMENTATION_ADDED: dict[str, set[str]] = {
    # asset_market_id 等子表统一补齐 deleted_by（V1.2 §6.2.3 决议吸收 V1.1）
    "ars.asset_market_id": {"deleted_by", "updated_by"},
    # asset_status_history 整表是实施侧补齐（V1.2 §6.3）
    "ars.asset_status_history": {"e_signature_id"},  # V1.1 §8 缺整表 DDL；这里只挑差异
    # ref 三表 deleted_by 已对齐 V1.1，但 substance_status_history 也含 e_signature_id
    "srs.substance_status_history": {"e_signature_id"},
    # mm.material_batch V1.2 修订八 §10.2 补齐 deleted_by + 整套 audit
    "mm.material_batch": {"deleted_by"},
    # P4.B-1：auth.refresh_token 整表是 V1.1 ARCH §7.2.1 目标实施；不在 DM §4 列出
    "auth.refresh_token": "WHOLE_TABLE",  # 直接整表豁免
    # M3.11/Batch G3.A 新增 meta 表（V1.2 §6.7 / ARCH12）
    "meta.lookup_value": "WHOLE_TABLE",
    "meta.system_config": "WHOLE_TABLE",
    # Phase 1 实施侧补齐：账号锁定时间戳（配 LOGIN_LOCK_DURATION_MINUTES 自动解锁）
    # V1.1 §4.2 字段集列了 status='locked' 状态但未列 locked_at；服务侧需要这个时间戳
    "auth.user": {"locked_at"},
    # Phase 2 实施侧补齐：V1.1 §9.2 表 DDL 未列 therapeutic_area/indication/program_director_id
    # 但 V1.2 修订五（line 12）已吸收这些字段进 V1.1（business 需要按疾病领域过滤项目）
    "prs.project": {"therapeutic_area", "indication", "program_director_id"},
}

# 字段命名豁免（部分 V1.1 期望字段在实施里换成了同义名 / 或者历史遗留差异）
FIELD_RENAMES: dict[str, dict[str, str]] = {
    # design_field → actual_field
    # 当前无 — 任何重命名都通过 V1.2 偏离说明显式登记
}

# 设计文档里 DDL 的字段命名审计 — 不要参与对比的"非字段"行
DDL_RESERVED_PREFIXES = (
    "CONSTRAINT", "CHECK", "FOREIGN KEY", "PRIMARY KEY", "UNIQUE",
    "REFERENCES", "ON DELETE", "ON UPDATE",
)


def parse_designed_tables(md_text: str) -> dict[str, set[str]]:
    """从 DM markdown 抓出所有 `CREATE TABLE schema.table (...)` 块的字段名集合。

    V1.1 markdown 的 CREATE TABLE 块通常被压成一行（docx 派生工具的副作用），
    所以匹配范围 = `CREATE TABLE\\s+(\\w+\\.\\w+)\\s*\\((.*?)\\)\\s*;`。
    """
    tables: dict[str, set[str]] = {}
    pattern = re.compile(
        r"CREATE TABLE\s+(\w+\.\w+)\s*\((.*?)\)\s*;",
        re.DOTALL,
    )
    for match in pattern.finditer(md_text):
        table_fqn = match.group(1).lower()
        body = match.group(2)
        fields = _extract_field_names(body)
        tables[table_fqn] = fields
    return tables


def _extract_field_names(ddl_body: str) -> set[str]:
    """从 CREATE TABLE 内部抓字段名。

    V1.1 docx 派生 markdown 把多行 DDL 压成一行 + 行内注释跨字段吞噬，让基于
    逗号切分的策略失效。这里改用"字段名 + 类型 token"直接匹配：
        identifier  TYPE[(args)]
    其中 TYPE 必须是已知 PG 类型集合中的一员，过滤掉注释里随机的英文单词。
    """
    pg_types = (
        "BIGINT", "INT", "INTEGER", "SMALLINT", "BIGSERIAL", "SERIAL",
        "VARCHAR", "TEXT", "CHAR",
        "BOOLEAN", "BOOL",
        "TIMESTAMP", "TIMESTAMPTZ", "DATE", "TIME",
        "JSONB", "JSON",
        "NUMERIC", "DECIMAL", "REAL", "DOUBLE",
        "UUID", "BYTEA", "INET", "CIDR",
    )
    # ([a-z_][a-z0-9_]*) 字段名 + 大量空白 + TYPE 关键字（不区分大小写，类型后可跟 (args)）
    pattern = re.compile(
        r"(?:^|[\s,(])([a-z_][a-z0-9_]*)\s+(" + "|".join(pg_types) + r")\b",
        re.IGNORECASE,
    )

    fields: set[str] = set()
    for m in pattern.finditer(ddl_body):
        name = m.group(1).lower()
        # 防呆：CONSTRAINT 关键字本身可能后接 BIGINT 等（罕见但要排除）
        if name in {
            "constraint", "primary", "foreign", "unique", "check",
            "references", "on", "table", "if", "not", "exists",
            "create",
        }:
            continue
        fields.add(name)
    return fields


def fetch_actual_tables(conn) -> dict[str, set[str]]:
    """从 information_schema 取实际所有业务表字段集"""
    actual: dict[str, set[str]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name, column_name
              FROM information_schema.columns
             WHERE table_schema IN ('auth','meta','audit','srs','prs','ars','mm','ref','staging')
               AND table_name <> 'alembic_version'
            """
        )
        for schema, table, column in cur.fetchall():
            fqn = f"{schema}.{table}".lower()
            actual.setdefault(fqn, set()).add(column.lower())
    return actual


def main() -> int:
    if not DM_MD.exists():
        print(f"ERROR：DM markdown 不存在：{DM_MD}", file=sys.stderr)
        return 2
    md_text = DM_MD.read_text(encoding="utf-8")
    designed = parse_designed_tables(md_text)

    # 应用 FIELD_RENAMES
    for table, mapping in FIELD_RENAMES.items():
        if table in designed:
            for design_name, actual_name in mapping.items():
                if design_name in designed[table]:
                    designed[table].remove(design_name)
                    designed[table].add(actual_name)

    db_url = os.getenv("DATABASE_URL_SYNC")
    if not db_url:
        # 默认连 dev 容器
        db_url = "postgresql://postgres:__REDACTED_POSTGRES_DBA_PASSWORD__@localhost:15432/cmab_mdm"
    print(f"# 连接 DB：{db_url.split('@')[-1]}")
    print(f"# 读取设计：{DM_MD.relative_to(ROOT)}（{len(designed)} 张设计表）")

    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.Error as e:
        print(f"ERROR：连接 DB 失败：{e}", file=sys.stderr)
        return 2

    try:
        actual = fetch_actual_tables(conn)
    finally:
        conn.close()
    print(f"# 实际 DB：{len(actual)} 张业务表")
    print()

    # ============== 对比 ==============
    all_tables = set(designed.keys()) | set(actual.keys())
    has_drift = False
    summary_lines: list[str] = []

    for fqn in sorted(all_tables):
        in_design = fqn in designed
        in_actual = fqn in actual
        designed_fields = designed.get(fqn, set())
        actual_fields = actual.get(fqn, set())

        # 已豁免：整表 WHITE_LIST
        impl_added = IMPLEMENTATION_ADDED.get(fqn)
        if impl_added == "WHOLE_TABLE":
            summary_lines.append(f"  豁免  {fqn}  （Phase 4 实施侧整表补齐，V1.2 修订八登记）")
            continue
        if fqn in EXPECTED_UNIMPLEMENTED:
            if in_actual:
                summary_lines.append(f"  ⚠️ {fqn}  V1.1 列出预期未实施但 DB 已存在 → 请确认是否提前落地")
            else:
                summary_lines.append(f"  豁免  {fqn}  （V1.1 列出，Phase 5+ 实施）")
            continue

        # 只设计无实施 → 缺失
        if in_design and not in_actual:
            has_drift = True
            summary_lines.append(f"  ❌ {fqn}  设计列出，DB 未建（需要 migration 落地）")
            continue
        # 只实施无设计 → DB 多余
        if in_actual and not in_design:
            has_drift = True
            summary_lines.append(f"  ❌ {fqn}  DB 存在，DM markdown 无设计（请确认 V1.2 偏离说明已登记）")
            continue

        # 两边都有：对比字段
        extra_in_db = actual_fields - designed_fields
        missing_in_db = designed_fields - actual_fields

        # 字段级豁免
        whitelist = impl_added if isinstance(impl_added, set) else set()
        extra_in_db = extra_in_db - whitelist

        if not extra_in_db and not missing_in_db:
            summary_lines.append(f"  ✓ {fqn}  ({len(actual_fields)} 字段对齐)")
            continue

        has_drift = True
        if extra_in_db:
            summary_lines.append(
                f"  ❌ {fqn}  DB 多余字段：{sorted(extra_in_db)}"
            )
        if missing_in_db:
            summary_lines.append(
                f"  ❌ {fqn}  DB 缺失字段：{sorted(missing_in_db)}"
            )

    print("# 对比结果")
    print("=" * 70)
    for line in summary_lines:
        print(line)
    print("=" * 70)

    if has_drift:
        print("\n❌ schema 与设计基线存在偏离（详见上表 ❌ 行）。请检查：")
        print("   1. 偏离是否已在 docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md 登记？")
        print("   2. 若已登记 → 把该表加入本脚本 IMPLEMENTATION_ADDED 或 FIELD_RENAMES")
        print("   3. 若未登记 → 回归到 V1.1 DDL 或追加 V1.2 修订条目")
        return 1
    print("\n✓ schema 与 V1.1 设计基线完全对齐（含 V1.2 已登记的实施侧补齐项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
