# admin 鉴权 —— 已从「共享密码 + x-admin-token」切换为 MDM JWT 角色鉴权。
# verify_admin 保留原名供 employees.py / methods.py 挂 Depends，
# 实际逻辑在 app.core.auth.require_admin（需 CMC_LIMS_ADMIN / SYS_ADMIN 角色）。
from app.core.auth import require_admin as verify_admin

__all__ = ["verify_admin"]
