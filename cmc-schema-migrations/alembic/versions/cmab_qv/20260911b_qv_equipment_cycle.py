"""验证周期表改成「一台设备一行、两列周期」+ 接 MDM 设备台账（2026-09-11 晚）

负责人看过第一版后纠正：他要的不是「一个设备一种活动一行」，而是**一张大表**——
一行 = 一台设备（或一个厂房/系统），后面两列分别填 `再确认周期` 和 `再评估周期`（都按月），
其余列是基础信息（编号、名称、类型、使用部门、厂区…）供筛选，MDM 里设备有增改这边能同步过来。

所以把上一版 `validation.validation_cycle`（一个对象 × 一种活动一行）整张换掉。
上一版在 Linux 上是 0 行、Mac 上只有试跑数据，直接 drop 不会丢真数据。

**这张表不是设备台账**：设备主数据权威源仍是 MDM `cmab_mdm.eqp.equipment`（总纲 §1 铁律 3）。
基础信息列是 MDM 同步下来的**快照**（`source='mdm'` 的行由同步覆盖，本地别手改），
本表自己管的只有两列周期 + 依据 + 备注 + 启停用。

身份怎么认（三种行并存，所以是三个部分唯一索引，不是一个主键）：
- MDM 同步来的：`mdm_equipment_code`（EQP-yyyy-NNNNNN）唯一
- 主计划里有编号但 MDM 还没收录的（生产设备大多如此）：`equipment_no` 唯一；
  将来 MDM 收了它，同步按 `equipment_no` 认领同一行，补上 code，不会多出一行
- 厂房 / 空调系统 / 房间这类没编号的：`(equipment_name, user_dept_code)` 唯一
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "qv_equipment_cycle"
down_revision = "qv_cycle_and_next_due"
branch_labels = None
depends_on = None

SCHEMA = "validation"
CYCLE_STATUSES = ("启用", "停用")
SOURCES = ("mdm", "plan", "manual")


def upgrade() -> None:
    op.drop_table("validation_cycle", schema=SCHEMA)

    op.create_table(
        "equipment_cycle",
        sa.Column("cycle_id", sa.BigInteger, primary_key=True, autoincrement=True),
        # ── 身份 ──
        sa.Column(
            "mdm_equipment_code", sa.String(32),
            comment="MDM 设备ID（EQP-yyyy-NNNNNN），同步来的才有；跨库不建外键",
        ),
        sa.Column(
            "equipment_no", sa.String(64),
            comment="设备编号（业务号，如 CC1-SC-009）—— 主计划里写的就是它，对账靠它",
        ),
        sa.Column("equipment_name", sa.String(255), nullable=False, comment="名称"),
        sa.Column("user_dept_code", sa.String(32), comment="使用部门代码，区分没编号的同名对象"),
        # ── 本表自己管的：两列周期 ──
        sa.Column(
            "reconfirm_months", sa.SmallInteger,
            comment="再确认周期（月）。空 = 还没人填，程序不猜、不算下次日期",
        ),
        sa.Column("reassess_months", sa.SmallInteger, comment="再评估周期（月）。空同上"),
        sa.Column("cycle_basis", sa.String(200), comment="周期依据，如「风险评估 RA-2026-007」"),
        sa.Column("notes", sa.Text),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="启用",
            comment="本平台是否还跟这台：启用 / 停用（报废、不再验证的改停用，不删）",
        ),
        # ── MDM 快照（source='mdm' 的行由同步覆盖，本地别手改）──
        sa.Column("category", sa.String(64), comment="类型（MDM 五分类；厂房/系统这类可自填）"),
        sa.Column("model", sa.String(200), comment="型号"),
        sa.Column("manufacturer", sa.String(100), comment="厂家"),
        sa.Column("department", sa.String(64), comment="使用部门（MDM）"),
        sa.Column("site", sa.String(64), comment="厂区"),
        sa.Column("room", sa.String(100), comment="房间 / 存放位置"),
        sa.Column("criticality", sa.String(16), comment="分级：A/B/C 或 关键/一般"),
        sa.Column("mdm_status", sa.String(16), comment="MDM 里的状态：active / retired"),
        sa.Column("mdm_synced_at", sa.DateTime(timezone=True), comment="最近一次从 MDM 同步的时间"),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="manual",
            comment="mdm = MDM 同步来的；plan = 主计划里有、MDM 还没有；manual = 人工建的",
        ),
        # ── 审计 ──
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False, comment="操作人工号（JWT username 快照）"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "status IN ('" + "','".join(CYCLE_STATUSES) + "')", name="ck_equipment_cycle_status"
        ),
        sa.CheckConstraint(
            "source IN ('" + "','".join(SOURCES) + "')", name="ck_equipment_cycle_source"
        ),
        # 1 个月到 10 年；填 365 那种（按天填）挡在门外
        sa.CheckConstraint(
            "reconfirm_months IS NULL OR (reconfirm_months BETWEEN 1 AND 120)",
            name="ck_equipment_cycle_reconfirm_range",
        ),
        sa.CheckConstraint(
            "reassess_months IS NULL OR (reassess_months BETWEEN 1 AND 120)",
            name="ck_equipment_cycle_reassess_range",
        ),
        schema=SCHEMA,
        comment="设备验证周期表：一行 = 一台设备（或厂房/系统），两列周期（再确认 / 再评估，按月）。"
                "基础信息是 MDM eqp.equipment 的快照，本表不是设备台账。",
    )
    # 三种身份各自唯一（部分索引）：MDM 收录的 / 只有业务编号的 / 连编号都没有的
    op.create_index(
        "uq_equipment_cycle_mdm_code", "equipment_cycle", ["mdm_equipment_code"],
        schema=SCHEMA, unique=True, postgresql_where=sa.text("mdm_equipment_code IS NOT NULL"),
    )
    op.create_index(
        "uq_equipment_cycle_equipment_no", "equipment_cycle", ["equipment_no"],
        schema=SCHEMA, unique=True, postgresql_where=sa.text("equipment_no IS NOT NULL"),
    )
    op.create_index(
        "uq_equipment_cycle_name_dept", "equipment_cycle", ["equipment_name", "user_dept_code"],
        schema=SCHEMA, unique=True,
        postgresql_where=sa.text("equipment_no IS NULL AND mdm_equipment_code IS NULL"),
    )
    # 页面上按类型 / 部门 / 厂区筛
    op.create_index("ix_equipment_cycle_category", "equipment_cycle", ["category"], schema=SCHEMA)
    op.create_index("ix_equipment_cycle_department", "equipment_cycle", ["department"], schema=SCHEMA)
    op.create_index("ix_equipment_cycle_site", "equipment_cycle", ["site"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("equipment_cycle", schema=SCHEMA)
    # 回退只还原上一版的表结构骨架（那一版数据本就为空）
    op.create_table(
        "validation_cycle",
        sa.Column("cycle_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("equipment_no", sa.String(64)),
        sa.Column("object_name", sa.String(255)),
        sa.Column("user_dept_code", sa.String(32)),
        sa.Column(
            "object_key", sa.String(320),
            sa.Computed(
                "COALESCE(equipment_no, object_name || '@' || COALESCE(user_dept_code, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(16), nullable=False),
        sa.Column("cycle_months", sa.SmallInteger),
        sa.Column("cycle_basis", sa.String(200)),
        sa.Column("equipment_name", sa.String(255)),
        sa.Column("equipment_model", sa.String(200)),
        sa.Column("site", sa.String(32)),
        sa.Column("user_dept_name", sa.String(200)),
        sa.Column("status", sa.String(16), nullable=False, server_default="启用"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.UniqueConstraint("object_key", "activity_type", name="uq_validation_cycle_object_activity"),
        schema=SCHEMA,
    )
