**CMC LabOps Portal**

**React 前端迁移方案**

*Streamlit → React Migration Plan*

| | |
|---|---|
| **文档编号** | MIG-LABOPS-001 |
| **版本** | V1.2（修订历史见下表；文件名沿用 V1_0 不随版本改名） |
| **状态** | Draft |
| **发布日期** | 2026-05-19 |
| **编制** | CMC IT |
| **上位文档** | ARCH-LABOPS-001 V1.4 |
| **分类** | 内部技术文档 |

# 修订记录

| **版本** | **日期** | **修订人** | **修订内容** |
|---|---|---|---|
| V1.0 | 2026-05-19 | CMC IT | 初始版本 |
| V1.1 | 2026-06-04 | CMC IT | 认证对接 MDM：§2.1 中 /api/auth/change-password、/api/users*（除 /api/users/me）、/api/users/{id}/reset-password 已随本地用户体系移除，由 MDM Portal 承担；Phase 2 的"用户管理页/个人中心改密"不再在本系统实现；新增 /api/mdm/materials*（MDM 物料按需拉取） |
| V1.2 | 2026-06-06 | CMC IT | 消除与 V1.1 修订记录的矛盾：§2.1 表中已移除的认证/用户端点补"已移除"标注并修正复用结论；§2.1 补 MDM 物料集成端点、§2.2 补设备模块 MDM 集成端点（from-mdm / sync-mdm / batch-from-mdm / /api/mdm/equipments*），与 DM-LABOPS-001 V1.4 §7.2 对齐。注：本文档为迁移实施计划，迁移已完成，本次修订仅作归档勘误 |

## 适用范围

- 本文档为 CMC LabOps Portal 前端从 Streamlit 迁移到 React + Ant Design 的分阶段实施计划
- 覆盖迁移策略、优先级、API 复用分析、并行运行方案、风险与回滚

# 1. 迁移目标

## 1.1 为什么迁移

| **维度** | **Streamlit 现状** | **React 目标** |
|---|---|---|
| 组件丰富度 | 有限，复杂交互需大量 workaround | Ant Design 5 提供完整企业级组件 |
| 表格能力 | st.dataframe 功能有限 | Ant Design Table：排序、筛选、列配置、虚拟滚动 |
| 路由 | st.navigation 简单路由 | React Router：嵌套路由、权限守卫、URL 参数 |
| 权限控制 | 页面级粗粒度 | 组件级细粒度（按钮、列、Tab） |
| 响应性能 | 每次交互全页面重渲 | 局部更新，TanStack Query 缓存 |
| 与 MDM 一致性 | 完全不同的 UI 体系 | 视觉风格、组件、布局完全一致 |
| 可维护性 | Python + Streamlit 特定 API | 业界标准 React + TypeScript |
| 多人协作 | 困难（全局 session_state） | 标准前端工程化 |

## 1.2 迁移原则

1. **不断服务**：迁移期间 Streamlit 旧前端持续运行，用户可随时切换
2. **API 不变**：后端 API 路径、参数、响应格式保持不变，React 调用同一后端
3. **逐页迁移**：按优先级逐页实现 React 版本，不做一次性全量切换
4. **数据一致**：两个前端共享同一数据库，任何一端的操作另一端即时可见
5. **可回滚**：任何阶段发现问题，可退回 Streamlit，零数据损失

# 2. API 复用分析

## 2.1 可直接复用的 API（无需修改）

| **API** | **方法** | **用途** | **React 直接调用** |
|---|---|---|---|
| /api/auth/login | POST | 登录 | ✓ |
| /api/auth/logout | POST | 登出 | ✓ |
| /api/users/me | GET | 当前用户 | ✓ |
| ~~/api/auth/change-password~~ | ~~POST~~ | ~~改密~~ | ✗ V1.1 已移除（MDM 承担） |
| /api/materials | GET | 物料列表 | ✓ |
| /api/materials | POST | 新增物料 | ✓ |
| /api/materials/{id} | GET | 物料详情 | ✓ |
| /api/materials/{id} | PATCH | 编辑物料 | ✓ |
| /api/materials/{id}/deactivate | POST | 停用 | ✓ |
| /api/materials/{id}/activate | POST | 启用 | ✓ |
| /api/categories | GET | 分类字典 | ✓ |
| /api/units | GET | 单位字典 | ✓ |
| /api/batches | GET | 批次列表 | ✓ |
| /api/batches | POST | 创建批次+首次入库 | ✓ |
| /api/batches/{id} | GET | 批次详情 | ✓ |
| /api/inventory/in | POST | 追加入库 | ✓ |
| /api/inventory/out | POST | 出库 | ✓ |
| /api/inventory/adjust | POST | 盘点调整 | ✓ |
| /api/inventory/transfer | POST | 移库 | ✓ |
| /api/inventory/txns | GET | 流水查询 | ✓ |
| /api/stock/by-material | GET | 按物料汇总 | ✓ |
| /api/stock/by-batch | GET | 按批次明细 | ✓ |
| /api/stock/alerts/expiry | GET | 效期预警 | ✓ |
| /api/stock/alerts/low-stock | GET | 低库存预警 | ✓ |
| /api/locations | GET | 位置列表 | ✓ |
| /api/locations | POST | 新增位置 | ✓ |
| /api/import/materials/dry-run | POST | 导入预览 | ✓ |
| /api/import/materials/commit | POST | 正式导入 | ✓ |
| /api/import/logs | GET | 导入历史 | ✓ |
| ~~/api/users~~ | ~~GET/POST~~ | ~~用户列表/新建~~ | ✗ V1.1 已移除（MDM 承担） |
| ~~/api/users/{id}~~ | ~~PATCH~~ | ~~编辑用户~~ | ✗ V1.1 已移除（MDM 承担） |
| ~~/api/users/{id}/reset-password~~ | ~~POST~~ | ~~重置密码~~ | ✗ V1.1 已移除（MDM 承担） |
| /api/audit/logs | GET | 审计日志 | ✓ |
| /api/mdm/materials | GET | MDM 物料搜索（透传，V1.1 新增） | ✓ |
| /api/mdm/materials/{code} | GET | MDM 物料详情（透传，V1.1 新增） | ✓ |
| /api/materials/from-mdm/{code} | POST | 从 MDM 引用建物料（V1.1 新增） | ✓ |

**结论（V1.2 修订）：除 V1.1 移交 MDM 的 5 个用户/改密端点外，其余端点全部可直接复用。**

## 2.2 需要新增的后端 API（设备模块）

| **API** | **方法** | **用途** |
|---|---|---|
| /api/equipment | GET | 设备列表 |
| /api/equipment | POST | 新增设备（后端 API 兜底，前端无入口 — V1.3） |
| /api/mdm/equipments | GET | MDM 设备搜索（透传，V1.2 补记） |
| /api/mdm/equipments/{code} | GET | MDM 设备详情（透传，V1.2 补记） |
| /api/equipment/from-mdm/{code} | POST | 从 MDM 引用建档（V1.2 补记） |
| /api/equipment/{id}/sync-mdm | POST | 从 MDM 刷新快照（V1.4 功能，V1.2 补记） |
| /api/equipment/batch-from-mdm | POST | 从 MDM 批量引用建档（V1.4 功能，V1.2 补记） |
| /api/equipment/{id} | GET | 设备详情 |
| /api/equipment/{id} | PATCH | 编辑设备 |
| /api/equipment/{id}/deactivate | POST | 报废设备 |
| /api/equipment/{id}/calibrations | GET | 校验记录列表 |
| /api/equipment/{id}/calibrations | POST | 新增校验记录 |
| /api/equipment/{id}/maintenances | GET | 维护记录列表 |
| /api/equipment/{id}/maintenances | POST | 新增维护记录 |
| /api/equipment/{id}/repairs | GET | 维修记录列表 |
| /api/equipment/{id}/repairs | POST | 新增维修记录 |
| /api/equipment/{id}/warranty | GET | 保修信息 |
| /api/equipment/{id}/warranty | PUT | 更新保修信息 |
| /api/equipment/{id}/attachments | GET | 附件列表 |
| /api/equipment/{id}/attachments | POST | 上传附件 |
| /api/equipment/{id}/attachments/{aid} | DELETE | 删除附件 |
| /api/alerts | GET | 聚合预警（物料+设备） |

## 2.3 后端需要调整的地方

| **调整项** | **原因** | **影响范围** | **优先级** |
|---|---|---|---|
| 增加 CORS 配置 | React 开发时 dev server 在不同端口 | main.py 加 CORSMiddleware | P0 |
| 认证 token 通过 Authorization header | 现有已支持 | 无需改动 | — |
| 文件上传 API 适配 | 设备附件上传 + 导入 Excel | 新增 multipart 处理 | P1 |
| 后端模块化重组 | routers/*.py → material/router.py 等 | 内部重组，API 路径不变 | P2 |
| RBAC 权限中间件 | 从硬编码角色升级 | 新增 permissions.py | P2 |

# 3. 分阶段迁移计划

## 3.1 Phase 1：脚手架 + 核心高频页面（第 3-6 周）

### 目标
搭建 React 项目基础，迁移 3 个最高频页面，让用户开始使用新前端。

### 交付物

| **序号** | **任务** | **说明** |
|---|---|---|
| 1.1 | React 项目初始化 | Vite + React 18 + TypeScript + Ant Design 5 + pnpm |
| 1.2 | 登录页 | /login，调用现有 /api/auth/login |
| 1.3 | 主布局 | Header + Sidebar + Content Area + Breadcrumb |
| 1.4 | 路由配置 | React Router + ProtectedRoute 权限守卫 |
| 1.5 | API 客户端 | Axios 实例 + 拦截器（token 注入、401 跳转） |
| 1.6 | 状态管理 | Zustand authStore + TanStack Query 配置 |
| 1.7 | 库存查询页 | /material/stock — 最高频页面，只读，风险最低 |
| 1.8 | 库存预警页 | /material/alerts — 高频，只读 |
| 1.9 | 入库登记页 | /material/intake — 高频写操作，验证表单能力 |

### 为什么先迁这 3 页

| **页面** | **理由** |
|---|---|
| 库存查询 | 每天被所有人使用，只读 API，迁移风险最低，最快体现 React 表格优势 |
| 库存预警 | 同上，且可展示 Tag 状态色彩系统 |
| 入库登记 | 最高频写操作，验证 React 表单 + 级联选择 + API 提交完整链路 |

### 里程碑

- M1.1：React 项目可本地启动，登录成功跳 Dashboard 占位
- M1.2：库存查询页功能完整，数据与 Streamlit 完全一致
- M1.3：入库登记可正常提交

## 3.2 Phase 2：物料模块完整迁移（第 7-10 周）

### 交付物

| **序号** | **任务** | **说明** |
|---|---|---|
| 2.1 | 出库登记页 | /material/outgoing |
| 2.2 | 物料管理页 | /material/list — 含新增、编辑、停用/启用 |
| 2.3 | 盘点调整页 | /material/adjust |
| 2.4 | 移库页 | /material/transfer |
| 2.5 | 物料导入页 | /material/import — 文件上传 + 干跑预览 + 确认导入 |
| 2.6 | ~~用户管理页~~ → 审计日志页 | /admin/audit（用户管理移至 MDM Portal，V1.1） |
| 2.7 | ~~个人中心(修改密码)~~ | 改密在 MDM Portal 完成，本系统不实现（V1.1） |

### 里程碑

- M2.1：物料管理 CRUD 功能完整
- M2.2：所有 9 个 Streamlit 页面在 React 中有完整对应
- M2.3：内部用户验收测试（UAT）通过

### Phase 2 结束后

此时 React 前端已完整覆盖 Streamlit 所有功能。可以：
- 通知用户切换到 React 前端
- Streamlit 降为备用（保留运行但不做新功能）
- 在 Streamlit 首页加提示："新版本已上线，请使用 http://xxx:80"

## 3.3 Phase 3：设备管理模块（第 11-16 周）

### 交付物

| **序号** | **任务** | **说明** |
|---|---|---|
| 3.1 | 设备数据库 schema | equipment_mgmt schema + 7 张表 |
| 3.2 | 设备后端 API | /api/equipment/* 全套 CRUD |
| 3.3 | 设备台账列表页 | /equipment/list |
| 3.4 | 设备详情页 | /equipment/:id — 6 Tab |
| 3.5 | 新增/编辑设备表单 | /equipment/new, /equipment/:id/edit |
| 3.6 | 校验/维护/维修记录表单 | 弹窗或抽屉表单 |
| 3.7 | 附件上传/预览 | 设备附件管理 |
| 3.8 | 设备预警 API | 校验/维护/保修到期查询 |

### 里程碑

- M3.1：能新建设备，录入校验记录
- M3.2：设备详情 6 Tab 功能完整
- M3.3：设备预警可正常展示

## 3.4 Phase 4：统一门户 + 收尾（第 17-20 周）

### 交付物

| **序号** | **任务** | **说明** |
|---|---|---|
| 4.1 | Dashboard | 统计卡片 + 待处理告警 + 快捷入口 |
| 4.2 | 预警中心 | 聚合物料预警 + 设备预警 |
| 4.3 | RBAC 升级 | labops_auth schema + 角色权限管理 UI |
| 4.4 | 审计日志升级 | labops_audit schema + 独立审计页 |
| 4.5 | Streamlit 退役 | 停止 Streamlit 服务，清理旧代码 |
| 4.6 | Nginx 配置 | 生产级反向代理 + 静态资源服务 |

### 里程碑

- M4.1：Dashboard 上线
- M4.2：RBAC 权限管理完成
- M4.3：Streamlit 服务正式停止

# 4. 并行运行策略

## 4.1 迁移期间架构

```text
用户浏览器
   │
   ├──→ React 前端 (:80 或 :3000)  ──→ FastAPI (:8000) ──→ PostgreSQL
   │                                       ↑
   └──→ Streamlit 前端 (:8501) ───────────┘
                                    (共享同一后端和数据库)
```

### 关键保证

1. **数据一致性**：两个前端共享同一数据库，不存在数据同步问题
2. **认证独立**：两个前端各自管理 token（Streamlit 在 localStorage，React 在 memory/sessionStorage），互不干扰
3. **API 无改动**：后端 API 路径、参数、响应格式完全不变

## 4.2 用户切换指引

| **阶段** | **Streamlit** | **React** | **用户指引** |
|---|---|---|---|
| Phase 1 | 主入口（完整功能） | 测试入口（3 页面） | 内部测试人员使用 React |
| Phase 2 | 备用入口 | 主入口（完整功能） | 通知全员切换到 React |
| Phase 3 | 备用（可访问） | 主入口 + 设备模块 | React 独占新功能 |
| Phase 4 | 停止运行 | 唯一入口 | Streamlit 退役 |

# 5. React 项目技术方案

## 5.1 项目初始化

```bash
pnpm create vite cmc-labops-frontend --template react-ts
cd cmc-labops-frontend
pnpm add antd @ant-design/icons
pnpm add react-router-dom
pnpm add zustand @tanstack/react-query axios
pnpm add dayjs xlsx
```

## 5.2 目录结构

```text
src/
├── main.tsx
├── App.tsx                     路由配置
├── api/
│   ├── client.ts               Axios 实例 + 拦截器
│   ├── types.ts                API 类型定义
│   ├── auth.ts                 认证 API
│   ├── materials.ts            物料 API
│   ├── equipment.ts            设备 API
│   └── stock.ts                库存 API
├── stores/
│   └── authStore.ts            Zustand: token, user, login/logout
├── shared/
│   ├── layouts/
│   │   ├── MainLayout.tsx      Header + Sidebar + Content
│   │   ├── Header.tsx
│   │   └── Sidebar.tsx
│   └── components/
│       ├── StatusTag.tsx        统一状态 Tag
│       ├── PermissionGuard.tsx  权限守卫
│       └── PageHeader.tsx       页面标题 + 操作按钮
├── modules/
│   ├── auth/
│   │   ├── LoginPage.tsx
│   │   └── ChangePasswordPage.tsx
│   ├── material/
│   │   ├── MaterialList.tsx
│   │   ├── IntakeForm.tsx
│   │   ├── OutgoingForm.tsx
│   │   ├── TransferForm.tsx
│   │   ├── AdjustForm.tsx
│   │   ├── StockQuery.tsx
│   │   ├── StockAlerts.tsx
│   │   └── ImportPage.tsx
│   ├── equipment/
│   │   ├── EquipmentList.tsx
│   │   ├── EquipmentDetail.tsx
│   │   ├── EquipmentForm.tsx
│   │   └── tabs/
│   │       ├── CalibrationTab.tsx
│   │       ├── MaintenanceTab.tsx
│   │       ├── RepairTab.tsx
│   │       ├── WarrantyTab.tsx
│   │       └── AttachmentTab.tsx
│   ├── dashboard/
│   │   └── Dashboard.tsx
│   └── admin/
│       ├── UserManagement.tsx
│       └── AuditLogPage.tsx
└── routes/
    └── ProtectedRoute.tsx
```

## 5.3 API 客户端设计

```typescript
// api/client.ts
import axios from 'axios';
import { useAuthStore } from '../stores/authStore';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
});

// 请求拦截：注入 token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截：401 跳登录
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

## 5.4 认证状态管理

```typescript
// stores/authStore.ts
import { create } from 'zustand';

interface AuthState {
  token: string | null;
  user: { username: string; role: string } | null;
  login: (token: string, user: any) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: sessionStorage.getItem('labops_token'),
  user: JSON.parse(sessionStorage.getItem('labops_user') || 'null'),
  login: (token, user) => {
    sessionStorage.setItem('labops_token', token);
    sessionStorage.setItem('labops_user', JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    sessionStorage.removeItem('labops_token');
    sessionStorage.removeItem('labops_user');
    set({ token: null, user: null });
  },
}));
```

# 6. 风险与回滚方案

## 6.1 风险分析

| **风险** | **概率** | **影响** | **应对** |
|---|---|---|---|
| React 页面 bug 影响业务 | 中 | 高 | Streamlit 保留作为即时回退入口 |
| API 行为在两端不一致 | 低 | 中 | 共享同一 API，行为天然一致 |
| 前端开发进度延迟 | 中 | 中 | 按优先级迁移，高频页面优先 |
| 用户拒绝新 UI | 低 | 中 | React UI 与 MDM 风格一致，用户已有预期 |
| 文件上传功能兼容性 | 低 | 低 | Ant Design Upload 组件成熟 |
| 性能问题（大表格） | 低 | 低 | Ant Design Virtual Table 支持 |

## 6.2 回滚方案

**原则：任何阶段都可以回退到 Streamlit，零数据损失。**

| **场景** | **回滚操作** | **影响** |
|---|---|---|
| Phase 1 发现严重问题 | 通知用户继续使用 Streamlit | React 3 个页面回退，无数据影响 |
| Phase 2 UAT 不通过 | 暂缓切换，Streamlit 继续作为主入口 | 等修复后再切换 |
| Phase 3 设备模块有 bug | 设备模块独立于物料，可单独回退 | 物料模块不受影响 |
| Phase 4 Streamlit 退役后发现问题 | 重新启动 Streamlit 服务（代码和数据都在） | 5 分钟内恢复 |

回滚前提：
- Streamlit 代码不删除，保留在 frontend/ 目录
- systemd unit 文件保留（disable 而非删除）
- 数据库不做破坏性变更（新 schema 独立于旧 schema）

# 7. 总结

### 迁移时间线

```text
第 1-2 周    Phase 0: 设计文档（当前阶段）
第 3-6 周    Phase 1: React 脚手架 + 库存查询/预警/入库 (3 页面)
第 7-10 周   Phase 2: 物料模块完整迁移 (全部 9 页面)
第 11-16 周  Phase 3: 设备管理模块 (全新)
第 17-20 周  Phase 4: Dashboard + 预警中心 + RBAC + Streamlit 退役
```

### 关键数字

- 现有可复用 API：**32 个端点，零改动**
- 新增设备 API：**17 个端点**
- 后端必要调整：**仅 CORS 配置（1 行代码）**
- 迁移期间数据风险：**零**（共享同一数据库）
- 回滚时间：**5 分钟**（重新启动 Streamlit）
