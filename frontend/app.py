"""
文件: frontend/app.py
用途: Streamlit 主入口(导航首页)
说明:
    - 实际业务页面位于 frontend/pages/ 下,按文件名前的数字排序
    - Streamlit 会自动把 pages/*.py 渲染成左侧导航
"""
from __future__ import annotations

import streamlit as st

from utils import API_BASE_URL, api_get, APIError

st.set_page_config(
    page_title="CMC 物料管理系统",
    page_icon="📦",
    layout="wide",
)

st.title("📦 CMC 物料管理系统 (MVP)")
st.caption("部门级物料管理 — 物料导入 / 入库 / 出库 / 库存统计 / 预警")

# 后端连通性检查
status_col, msg_col = st.columns([1, 5])
with status_col:
    try:
        api_get("/health")
        st.success("后端连接正常 ✅")
    except APIError as e:
        st.error("后端不可达 ❌")
        st.caption(str(e))
with msg_col:
    st.info(f"后端地址: `{API_BASE_URL}` — API 文档: {API_BASE_URL}/docs")

st.markdown("---")

st.markdown(
    """
### 使用流程
1. **物料导入** — 首次使用时,上传公司物料代码 Excel
2. **物料管理** — 维护安全库存、停用/启用物料
3. **入库登记** — 录入实际批次和数量
4. **出库登记** — 日常出库扣减
5. **库存查询** — 按物料 / 按批次查看实时库存
6. **库存预警** — 关注效期、低库存

> 左侧导航选择具体功能。
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
"""
    )
