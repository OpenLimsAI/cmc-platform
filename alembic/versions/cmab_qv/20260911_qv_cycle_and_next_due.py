"""验证周期表 + 主计划「下次验证」列 + 需核对标记（2026-09-11）

负责人 2026-09-11 拍板：公司在册设备各自的验证周期单独一张表，验完一次就照周期
自动算出下次该验的日期，显示在验证主计划台账上。

三条口径（负责人当天确认，别改）：

1. **下次日期从实际完成日期起算**：完成日期 + N 个月，月末对不齐取当月最后一天
   （8.31 + 6 个月 = 2.28）。不是从原定期限起算。
2. **周期留空就不算**。没人填过周期的对象，台账那一格显示「未设周期」，程序不猜。
   例外：主计划原文写明「验证周期：6个月」的 16 条，导入时照抄建行（source='import'），
   这是照抄不是猜。
3. **算过的留痕**：`next_due_cycle_months` 存下当时用的是几个月，以后周期改了，
   已完成条目的历史日期不会莫名其妙跟着变（要重算由应用显式回算，且不动人工改过的）。

对象为什么不是「设备」：主计划 368 条里有 49 条是厂房、空调系统、房间这类，本来就没有
设备编号，但同样要按周期再验证。所以一行 = 一个**对象** + 一种活动：有编号的按编号认，
没编号的按「名称 + 使用部门代码」认（`object_key` 是数据库自己拼的，不用应用维护）。

本表**不是设备台账**：只存编号、周期、依据。名称是导入时的文本快照，设备主数据权威源
仍是 MDM `cmab_mdm.eqp.equipment`（总纲 §1 铁律 3）。MDM 目前主要收了研发的 463 台，
主计划里的生产设备大多还没进去，所以先以主计划出现过的 347 个编号打底，将来再对号。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "qv_cycle_and_next_due"
down_revision = "qv_plan_tables"
branch_labels = None
depends_on = None

SCHEMA = "validation"

ACTIVITY_TYPES = ("再确认", "再评估")
CYCLE_STATUSES = ("启用", "停用")


def upgrade() -> None:
    # ---------- 验证周期表 ----------
    op.create_table(
        "validation_cycle",
        sa.Column("cycle_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "equipment_no", sa.String(64),
            comment="设备编号（对应 MDM eqp.equipment.equipment_no，跨库不建外键）；厂房/系统这类没编号的留空",
        ),
        sa.Column("object_name", sa.String(255), comment="没有设备编号时的对象名称，如「南楼空调系统」"),
        sa.Column("user_dept_code", sa.String(32), comment="使用部门代码，用来区分不同部门的同名对象"),
        # 唯一键由数据库自己拼：有编号按编号，没编号按「名称@部门代码」
        sa.Column(
            "object_key", sa.String(320),
            sa.Computed(
                "COALESCE(equipment_no, object_name || '@' || COALESCE(user_dept_code, ''))",
                persisted=True,
            ),
            nullable=False,
            comment="对象唯一标识（数据库生成）：有编号=编号，没编号=名称@部门代码",
        ),
        sa.Column("activity_type", sa.String(16), nullable=False, comment="再确认 / 再评估，两种活动周期可以不同"),
        sa.Column(
            "cycle_months", sa.SmallInteger,
            comment="验证周期（月）。空 = 还没人填，程序不猜、不算下次日期",
        ),
        sa.Column("cycle_basis", sa.String(200), comment="周期依据，如「主计划原文注明」「风险评估 RA-2025-012」"),
        # 显示用快照，不作主数据
        sa.Column("equipment_name", sa.String(255), comment="对象名称快照（主数据在 MDM）"),
        sa.Column("equipment_model", sa.String(200), comment="型号快照"),
        sa.Column("site", sa.String(32), comment="厂区快照：南楼 / 北楼 / 祥泰路"),
        sa.Column("user_dept_name", sa.String(200), comment="使用部门原文快照"),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="启用",
            comment="启用 / 停用。设备报废或不再验证的改停用，不删（历史要可追）",
        ),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="manual",
            comment="import = 从主计划铺底建的；manual = 人在页面上建的",
        ),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False, comment="操作人工号（JWT username 快照）"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "activity_type IN ('" + "','".join(ACTIVITY_TYPES) + "')",
            name="ck_validation_cycle_activity_type",
        ),
        sa.CheckConstraint(
            "status IN ('" + "','".join(CYCLE_STATUSES) + "')", name="ck_validation_cycle_status"
        ),
        sa.CheckConstraint("source IN ('import','manual')", name="ck_validation_cycle_source"),
        sa.CheckConstraint(
            "equipment_no IS NOT NULL OR object_name IS NOT NULL",
            name="ck_validation_cycle_object_identified",
        ),
        # 1 个月到 10 年，超出这个范围多半是填错（填 365 当天数那种）
        sa.CheckConstraint(
            "cycle_months IS NULL OR (cycle_months BETWEEN 1 AND 120)",
            name="ck_validation_cycle_months_range",
        ),
        sa.UniqueConstraint("object_key", "activity_type", name="uq_validation_cycle_object_activity"),
        schema=SCHEMA,
        comment="验证周期表：一行 = 一个对象（设备/厂房/系统）+ 一种活动 + 多少个月。验完按它算下次日期。",
    )
    op.create_index("ix_validation_cycle_equipment_no", "validation_cycle", ["equipment_no"], schema=SCHEMA)
    op.create_index("ix_validation_cycle_site", "validation_cycle", ["site"], schema=SCHEMA)

    # ---------- 主计划：下次验证日期 ----------
    op.add_column(
        "plan_item",
        sa.Column("next_due_date", sa.Date, comment="下次验证日期 = 完成日期 + 周期（月）"),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column(
            "next_due_cycle_months", sa.SmallInteger,
            comment="算这个日期时用的周期（月）。周期表以后改了，这里不跟着变",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column(
            "next_due_source", sa.String(16),
            comment="auto = 程序按周期算的；manual = 人工改过的（回算时不动它）",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column("next_due_note", sa.Text, comment="人工改下次日期的原因"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_plan_item_next_due_source",
        "plan_item",
        "next_due_source IS NULL OR next_due_source IN ('auto','manual')",
        schema=SCHEMA,
    )
    op.create_index("ix_plan_item_next_due", "plan_item", ["next_due_date"], schema=SCHEMA)

    # ---------- 主计划：导入时看不懂的地方，落库跟踪 ----------
    # 以前只在导入预览里显示一次，关掉就找不着了；现在存下来，台账能筛、核完能打勾。
    op.add_column(
        "plan_item",
        sa.Column(
            "needs_review", sa.Boolean, nullable=False, server_default=sa.false(),
            comment="导入时有看不懂的地方，等验证部核对",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column(
            "import_issues", postgresql.JSONB,
            comment="导入时的核对项（字符串数组），如「期限列是文字说明、没有日期：每年进行再评估」",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), comment="核对完成时间"),
        schema=SCHEMA,
    )
    op.add_column(
        "plan_item",
        sa.Column("reviewed_by", sa.String(64), comment="核对人工号"),
        schema=SCHEMA,
    )
    # 待核对的是少数（354 行里 33 条），部分索引够用且小
    op.create_index(
        "ix_plan_item_needs_review", "plan_item", ["plan_year"],
        schema=SCHEMA, postgresql_where=sa.text("needs_review"),
    )


def downgrade() -> None:
    op.drop_index("ix_plan_item_needs_review", "plan_item", schema=SCHEMA)
    for col in ("reviewed_by", "reviewed_at", "import_issues", "needs_review"):
        op.drop_column("plan_item", col, schema=SCHEMA)

    op.drop_index("ix_plan_item_next_due", "plan_item", schema=SCHEMA)
    op.drop_constraint("ck_plan_item_next_due_source", "plan_item", schema=SCHEMA, type_="check")
    for col in ("next_due_note", "next_due_source", "next_due_cycle_months", "next_due_date"):
        op.drop_column("plan_item", col, schema=SCHEMA)

    op.drop_table("validation_cycle", schema=SCHEMA)
