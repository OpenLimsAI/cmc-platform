"""部门管理员（DEPT_ADMIN）+ 验证部四角色 + 可下放角色前缀白名单

Revision ID: 0055_dept_admin
Revises: 0054_session_policy
Create Date: 2026-09-10 01:00:00.000000

背景：验证部平台（qv-validation-platform，门户 /qv/）登录与角色都走 MDM，
验证部负责人要能自己管本部门的人（负责人 2026-09-10 拍板）。

本迁移只写数据、不改表结构：
  - auth.role 新增系统角色 DEPT_ADMIN（部门管理员，不挂 permission，能力由代码按角色码判定）
  - auth.role 新增验证部四角色 QV_ADMIN / QV_ENGINEER / QV_REVIEWER / QV_VIEWER
    （下游 qv 平台按 JWT.roles 解释；MDM 内不挂权限；is_system=FALSE 与 USP/LIMS 角色同口径）
  - meta.system_config 新增 dept_admin.delegable_role_prefixes = 'QV_'
    （部门管理员可挂/摘的角色码前缀，逗号分隔；系统管理→部门管理员 在线改）

幂等：role_code 走 partial unique（uq_role_code_active，0046）做 ON CONFLICT DO NOTHING；
已有同码角色不覆盖名称/描述。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0055_dept_admin"
down_revision: str | None = "0054_session_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_CODES = ("DEPT_ADMIN", "QV_ADMIN", "QV_ENGINEER", "QV_REVIEWER", "QV_VIEWER")
CONFIG_KEY = "dept_admin.delegable_role_prefixes"


def upgrade() -> None:
    op.execute("""
        INSERT INTO auth.role (role_code, role_name, description, is_system) VALUES
            ('DEPT_ADMIN', '部门管理员',
             '只能管理与自己同部门（auth.user.department 相同）的用户：查看、锁定/解锁、挂/摘白名单角色（系统管理→部门管理员，默认 QV_ 前缀）；不能新建用户/改密/改部门；本角色不含任何业务权限',
             TRUE),
            ('QV_ADMIN',    '验证部管理员', '验证部平台（/qv/）：部门级管理权限，按 JWT.roles 由 qv 平台解释', FALSE),
            ('QV_ENGINEER', '验证工程师',   '验证部平台（/qv/）：起草/执行验证文件，按 JWT.roles 由 qv 平台解释', FALSE),
            ('QV_REVIEWER', '验证复核人',   '验证部平台（/qv/）：复核/审批验证文件，按 JWT.roles 由 qv 平台解释', FALSE),
            ('QV_VIEWER',   '验证只读',     '验证部平台（/qv/）：只读查看，按 JWT.roles 由 qv 平台解释', FALSE)
        ON CONFLICT (role_code) WHERE deleted_at IS NULL DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO meta.system_config (config_key, config_value, value_type, description) VALUES
            ('{CONFIG_KEY}', 'QV_', 'string',
             '部门管理员（DEPT_ADMIN）可挂/摘的角色码前缀白名单，逗号分隔；SYS_ADMIN / DEPT_ADMIN 永不可下放')
        ON CONFLICT (config_key) DO NOTHING
    """)


def downgrade() -> None:
    codes = ", ".join(f"'{c}'" for c in ROLE_CODES)
    # 注意：会一并解除用户身上这五个角色（下游 qv 平台随之失去角色标签）
    op.execute(f"""
        DELETE FROM auth.user_role
         WHERE role_id IN (SELECT role_id FROM auth.role WHERE role_code IN ({codes}))
    """)
    op.execute(f"""
        DELETE FROM auth.role_permission
         WHERE role_id IN (SELECT role_id FROM auth.role WHERE role_code IN ({codes}))
    """)
    op.execute(f"DELETE FROM auth.role WHERE role_code IN ({codes})")
    op.execute(f"DELETE FROM meta.system_config WHERE config_key = '{CONFIG_KEY}'")
