"""
文件: frontend/app.py
用途: Streamlit 主入口 + 按角色动态构建 sidebar
说明:
    - 用 st.navigation 程序化注册 page;真实文件放在 views/(故意不叫
      pages/,以免 Streamlit 自动扫描 → 即使 st.stop() 早返,登录前 sidebar
      也会泄露所有文件名)
    - 未登录:只显示登录表单(sidebar 空,不暴露功能)
    - 已登录:
        - admin 看到全部 8 页 + 主页
        - user 只看到 物料管理(只读)/ 库存查询 / 库存预警
    - 每个 page 内的 require_admin/require_login 守卫**仍然保留**作为后端兜底
      (防止 URL 直接访问、防止 role 被管理员改后旧 session 还在跑)
"""
from __future__ import annotations

import streamlit as st

from utils import api_get, APIError, AuthError
from auth_helper import (
    get_user, is_admin, is_logged_in, needs_password_change,
    render_change_password_form, render_login_form, render_user_chip,
)

st.set_page_config(page_title="CMC 物料管理系统", page_icon="📦", layout="wide")

# ----------------------------------------------------------------------------
# 未登录 / 首次需改密 → 不构建导航,只显示对应表单
# ----------------------------------------------------------------------------
if not is_logged_in():
    st.title("📦 CMC 物料管理系统 (MVP)")
    st.caption("部门级物料管理 — 物料导入 / 入库 / 出库 / 库存统计 / 预警")
    render_login_form()
    st.stop()

if needs_password_change():
    st.title("🔑 修改密码")
    render_change_password_form()
    st.stop()


# ----------------------------------------------------------------------------
# 主页内容(嵌入到 st.Page 用)
# ----------------------------------------------------------------------------
def _home_page():
    user = get_user()
    st.title("📦 CMC 物料管理系统 (MVP)")
    st.caption("部门级物料管理 — 物料导入 / 入库 / 出库 / 库存统计 / 预警")

    status_col, msg_col = st.columns([1, 5])
    with status_col:
        try:
            api_get("/health")
            st.success("后端连接正常 ✅")
        except (APIError, AuthError) as e:
            st.error("后端不可达 ❌")
            st.caption(str(e))
    with msg_col:
        role_label = "管理员(全部权限)" if is_admin() else "普通用户(只读)"
        st.info(
            f"当前登录:**{user['username']}** · {role_label}。"
            " 后端 API 仅限服务器本机访问;Swagger `/docs` 通过 SSH 隧道,详见 README §10.B。"
        )

    st.markdown("---")

    if is_admin():
        st.markdown(
            """
### 使用流程(管理员)
1. **物料导入** — 上传公司物料代码 Excel
2. **物料管理** — 维护安全库存、停用/启用、新增/编辑物料
3. **入库登记** — 录入实际批次和数量
4. **出库登记** — 日常出库扣减
5. **库存查询** — 按物料 / 按批次查看实时库存
6. **库存预警** — 关注效期、低库存
7. **盘点调整** — 把账面修正为实际盘点数
8. **用户管理** — 用户 CRUD + 操作日志
"""
        )
    else:
        st.markdown(
            """
### 你可访问的功能(普通用户 = 只读)
- **物料管理** — 查询物料信息(不能编辑)
- **库存查询** — 按物料 / 按批次查看实时库存
- **库存预警** — 关注效期、低库存

> 入库 / 出库 / 盘点 / 物料导入 等写操作需要管理员权限。
"""
        )

    with st.expander("📌 关键设计原则"):
        st.markdown(
            """
- 物料代码 **保留前导 0**(以字符串存储)
- 库存数量从出入库流水**实时聚合**,绝不缓存
- N/A、空白统一视为 NULL,展示为 `-`
- 物料停用为**软删除**,历史出入库记录完整保留
- 数量字段统一 `Decimal`,杜绝浮点误差
- 登录用户即操作人,所有写操作记 audit_log
"""
        )


# ----------------------------------------------------------------------------
# 按角色构建导航
# ----------------------------------------------------------------------------
home = st.Page(_home_page, title="主页", icon="🏠", default=True, url_path="home")

# 所有人可见
p_material = st.Page("views/2_物料管理.py", title="物料管理", icon="🗂️")
p_stock    = st.Page("views/5_库存查询.py", title="库存查询", icon="📊")
p_alert    = st.Page("views/6_库存预警.py", title="库存预警", icon="⚠️")

# 仅 admin 可见
p_import   = st.Page("views/1_物料导入.py", title="物料导入", icon="📥")
p_in       = st.Page("views/3_入库登记.py", title="入库登记", icon="📥")
p_out      = st.Page("views/4_出库登记.py", title="出库登记", icon="📤")
p_adjust   = st.Page("views/7_盘点调整.py", title="盘点调整", icon="🧮")
p_users    = st.Page("views/8_用户管理.py", title="用户管理", icon="👤")

if is_admin():
    nav_pages = {
        "导览":       [home],
        "主数据":     [p_import, p_material],
        "出入库":     [p_in, p_out, p_adjust],
        "库存与预警": [p_stock, p_alert],
        "系统":       [p_users],
    }
else:
    nav_pages = {
        "导览":       [home],
        "主数据":     [p_material],
        "库存与预警": [p_stock, p_alert],
    }

# 顶部用户卡片(每次重渲都加,放 sidebar 上方)
render_user_chip()

pg = st.navigation(nav_pages)
pg.run()
