"""验证主计划三张表：计划条目 / 条目↔设备 / 延期记录（2026-09-11）

负责人 2026-09-11 拍板开工。对应验证部平台 `/qv/tasks` 验证主计划台账 + `/qv/dashboard` 看板。
数据来源：验证部现有的《2026年验证主计划.xlsx》（3 个 Sheet = 3 个厂区，354 条）。

三个设计判断（照负责人确认的口径，别改）：

1. **一行一件事**。Excel 一行有时是两件事：6 个月周期的设备一年做两次挤在一行；
   隧道烘箱按规格分了 5 行其实是同一台设备。本表一条 = 一台(组)设备 + 一次活动 +
   一个到期日，6 个月周期的拆两条。这样「本月该做几件」才算得准。

2. **延期单独记，不覆盖原期限**。Excel 是把历史塞进一格
   （「2026.03.18 延期至2026.04.18，延期至2026.05.17」）。这里 `due_date` 原定期限
   写死不动，每延一次往 `plan_extension` 写一条；`effective_due_date` 是当前有效期限
   （= 最后一次延期的日期，没延过就等于 due_date），冗余在主表上只为查询快，
   由应用在写延期时同步维护。全表 22 条延期过，最多延 2 次。

3. **状态算出来，不存**。未开始/进行中/已完成/已逾期 由
   completed_date、effective_due_date、今天 三者推出，不设 status 列 —— 让人填状态
   一定会忘记改。

设备只存编号（`equipment_no`），**不建设备表、不建跨库外键**：设备台账权威源是
MDM `cmab_mdm.eqp.equipment`（总纲 §1 铁律 3）。设备名称/型号在本表是**导入时的文本
快照**，只为台账页显示和 MDM 尚未收录时仍可用，不作为主数据。

待办（负责人 2026-09-11：后期完善）：报告编号 `report_no` 目前只存不生成。
公司「项目文件类别代码」共 14 个（RQ 再确认 / OT 其他 / IQ / OQ / PQ …），
将来按 VR-<类别码>-<部门>-<年><序号> 自动出建议号、允许人工改。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "qv_plan_tables"
down_revision = "cmab_qv_baseline"
branch_labels = None
depends_on = None

SCHEMA = "validation"

# 活动类型：Excel 里南楼写「再确认/再评估」，北楼与祥泰路写「周期性再确认/周期性再评估」，
# 同义 —— 导入时归一到这两个值。
ACTIVITY_TYPES = ("再确认", "再评估")
# 合格证：Excel 原文有「无需发放」「04.21已发」和空，归一成三态（原文留 cert_note）。
CERT_STATUSES = ("无需发放", "已发放", "待发放")


def upgrade() -> None:
    # ---------- 计划条目 ----------
    op.create_table(
        "plan_item",
        sa.Column("plan_item_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("plan_year", sa.SmallInteger, nullable=False, comment="计划年度，如 2026"),
        sa.Column("site", sa.String(32), nullable=False, comment="厂区：南楼 / 北楼 / 祥泰路"),
        # 使用部门：Excel 原文形如「生产一部（MD01）」「G79北楼四楼生产五部（MD05）…」「洗衣房」。
        # 代码单独抽出来对齐 MDM auth.user.department / eqp.equipment.department；原文保留。
        sa.Column("user_dept_code", sa.String(32), comment="使用部门代码，如 MD01；抽不出来则空"),
        sa.Column("user_dept_name", sa.String(200), nullable=False, comment="使用部门原文（Excel 分块标题）"),
        sa.Column(
            "owner_dept", sa.String(32), nullable=False,
            comment="责任部门：QV = 验证部自己做；其余为使用部门自己做（如 MD01/QC/FF1）",
        ),
        # 设备：编号在 plan_item_equipment（一条计划可能挂多台，如传递窗一行 9 个编号）
        sa.Column("equipment_name", sa.String(255), comment="设备名称（导入快照，主数据在 MDM）"),
        sa.Column("equipment_model", sa.String(200), comment="设备型号（导入快照）"),
        sa.Column("activity_type", sa.String(16), nullable=False, comment="再确认 / 再评估"),
        # 期限
        sa.Column("due_date", sa.Date, comment="原定期限，写死不动；空 = 期限列是「/」或纯文字说明"),
        sa.Column(
            "effective_due_date", sa.Date,
            comment="当前有效期限 = 最后一次延期的日期，没延过等于 due_date；逾期判断用这个",
        ),
        sa.Column("due_note", sa.Text, comment="期限列原文（「/」「每年进行再评估」「(验证周期：6个月)」等原样保留）"),
        sa.Column("planned_ym", sa.String(7), comment="建议开展月份 YYYY-MM，看板月度柱子用"),
        sa.Column("planned_note", sa.String(200), comment="建议开展时间原文（可能是「2026.01/2026.07/2027.01」）"),
        # 完成
        sa.Column("completed_date", sa.Date, comment="完成日期；有值即视为已完成"),
        sa.Column("report_no", sa.String(64), comment="验证报告编号，如 VR-RQ-DS1-2026005"),
        sa.Column(
            "in_progress", sa.Boolean, nullable=False, server_default=sa.false(),
            comment="进行中（Excel 完成情况写「进行中」）",
        ),
        sa.Column("progress_note", sa.Text, comment="完成情况跟踪原文"),
        # 合格证
        sa.Column("cert_status", sa.String(16), comment="无需发放 / 已发放 / 待发放"),
        sa.Column("cert_note", sa.String(100), comment="合格证原文，如「04.21已发」"),
        # 溯源
        sa.Column("source_sheet", sa.String(64), comment="导入来源 Sheet"),
        sa.Column("source_row", sa.Integer, comment="导入来源 Excel 行号"),
        sa.Column("import_batch", sa.String(32), comment="导入批次号"),
        sa.Column("notes", sa.Text),
        # 审计
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False, comment="操作人工号（JWT username 快照，不建外键）"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "activity_type IN ('" + "','".join(ACTIVITY_TYPES) + "')",
            name="ck_plan_item_activity_type",
        ),
        sa.CheckConstraint(
            "cert_status IS NULL OR cert_status IN ('" + "','".join(CERT_STATUSES) + "')",
            name="ck_plan_item_cert_status",
        ),
        # 延期只能往后：有效期限不早于原定期限
        sa.CheckConstraint(
            "effective_due_date IS NULL OR due_date IS NULL OR effective_due_date >= due_date",
            name="ck_plan_item_effective_due_not_before_due",
        ),
        schema=SCHEMA,
        comment="验证主计划条目：一条 = 一台(组)设备 + 一次活动 + 一个到期日。状态不存，由完成日期/有效期限/今天算出。",
    )
    # 台账页默认按 年度+厂区 筛，看板按 月份 / 责任部门 / 有效期限 统计
    op.create_index("ix_plan_item_year_site", "plan_item", ["plan_year", "site"], schema=SCHEMA)
    op.create_index("ix_plan_item_effective_due", "plan_item", ["effective_due_date"], schema=SCHEMA)
    op.create_index("ix_plan_item_planned_ym", "plan_item", ["planned_ym"], schema=SCHEMA)
    op.create_index("ix_plan_item_owner_dept", "plan_item", ["owner_dept"], schema=SCHEMA)

    # ---------- 条目 ↔ 设备编号 ----------
    op.create_table(
        "plan_item_equipment",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("plan_item_id", sa.BigInteger, nullable=False),
        sa.Column(
            "equipment_no", sa.String(64), nullable=False,
            comment="设备编号，对应 MDM eqp.equipment.equipment_no；跨库不建外键",
        ),
        sa.ForeignKeyConstraint(
            ["plan_item_id"], [f"{SCHEMA}.plan_item.plan_item_id"],
            name="fk_plan_item_equipment_item", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("plan_item_id", "equipment_no", name="uq_plan_item_equipment"),
        schema=SCHEMA,
        comment="一条计划挂的设备编号（传递窗、层流罩这类一行挂 5~9 个编号）",
    )
    op.create_index("ix_plan_item_equipment_no", "plan_item_equipment", ["equipment_no"], schema=SCHEMA)

    # ---------- 延期记录 ----------
    op.create_table(
        "plan_extension",
        sa.Column("extension_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("plan_item_id", sa.BigInteger, nullable=False),
        sa.Column("from_date", sa.Date, comment="延期前的有效期限"),
        sa.Column("to_date", sa.Date, nullable=False, comment="延到哪天"),
        sa.Column("reason", sa.Text, comment="延期原因，如「无生产计划，处于停机状态」"),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="manual",
            comment="import = 从 Excel 期限列的延期链解析出来的历史；manual = 系统里申请的",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=False, comment="操作人工号；导入的历史记 import"),
        sa.Column("created_by_name", sa.String(64), comment="操作人姓名快照"),
        sa.ForeignKeyConstraint(
            ["plan_item_id"], [f"{SCHEMA}.plan_item.plan_item_id"],
            name="fk_plan_extension_item", ondelete="CASCADE",
        ),
        sa.CheckConstraint("source IN ('import','manual')", name="ck_plan_extension_source"),
        sa.CheckConstraint("from_date IS NULL OR to_date >= from_date", name="ck_plan_extension_forward"),
        schema=SCHEMA,
        comment="延期记录：每延一次一条，原定期限不覆盖（GMP 可追溯）",
    )
    op.create_index("ix_plan_extension_item", "plan_extension", ["plan_item_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("plan_extension", schema=SCHEMA)
    op.drop_table("plan_item_equipment", schema=SCHEMA)
    op.drop_table("plan_item", schema=SCHEMA)
