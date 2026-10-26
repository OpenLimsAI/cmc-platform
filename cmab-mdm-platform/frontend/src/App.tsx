import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { AppErrorBoundary } from './shared/components/AppErrorBoundary';
import { AppUpdateWatcher } from './shared/appUpdate';
// 首屏/框架级组件保持即时加载（登录页、布局、守卫、404），其余页面懒加载
import { LoginPage } from './modules/auth/pages/LoginPage';
import { MainLayout } from './shared/layouts/MainLayout';
import { ProtectedRoute } from './routes/ProtectedRoute';
import { FullAdminRoute } from './routes/FullAdminRoute';
import { HomeRedirect } from './routes/HomeRedirect';
import { PMProjectContextPage } from './modules/projects/pages/PMProjectContextPage';
import { NotFoundPage } from './modules/common/NotFoundPage';

// 路由级懒加载：每个页面打成独立 chunk，按需下载（命名导出→default 适配）
const DashboardPage = lazy(() =>
  import('./modules/dashboard/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const SubstanceListPage = lazy(() =>
  import('./modules/substances/pages/SubstanceListPage').then((m) => ({
    default: m.SubstanceListPage,
  })),
);
const SubstanceCreatePage = lazy(() =>
  import('./modules/substances/pages/SubstanceCreatePage').then((m) => ({
    default: m.SubstanceCreatePage,
  })),
);
const SubstanceDetailPage = lazy(() =>
  import('./modules/substances/pages/SubstanceDetailPage').then((m) => ({
    default: m.SubstanceDetailPage,
  })),
);
const SubstanceEditPage = lazy(() =>
  import('./modules/substances/pages/SubstanceEditPage').then((m) => ({
    default: m.SubstanceEditPage,
  })),
);
const ChangePasswordPage = lazy(() =>
  import('./modules/auth/pages/ChangePasswordPage').then((m) => ({ default: m.ChangePasswordPage })),
);
const ProjectListPage = lazy(() =>
  import('./modules/projects/pages/ProjectListPage').then((m) => ({ default: m.ProjectListPage })),
);
const ProjectCreatePage = lazy(() =>
  import('./modules/projects/pages/ProjectCreatePage').then((m) => ({
    default: m.ProjectCreatePage,
  })),
);
const ProjectDetailPage = lazy(() =>
  import('./modules/projects/pages/ProjectDetailPage').then((m) => ({
    default: m.ProjectDetailPage,
  })),
);
const ProjectEditPage = lazy(() =>
  import('./modules/projects/pages/ProjectEditPage').then((m) => ({ default: m.ProjectEditPage })),
);
const AssetListPage = lazy(() =>
  import('./modules/assets/pages/AssetListPage').then((m) => ({ default: m.AssetListPage })),
);
const AssetCreatePage = lazy(() =>
  import('./modules/assets/pages/AssetCreatePage').then((m) => ({ default: m.AssetCreatePage })),
);
const AssetDetailPage = lazy(() =>
  import('./modules/assets/pages/AssetDetailPage').then((m) => ({ default: m.AssetDetailPage })),
);
const AssetEditPage = lazy(() =>
  import('./modules/assets/pages/AssetEditPage').then((m) => ({ default: m.AssetEditPage })),
);
const MaterialListPage = lazy(() =>
  import('./modules/materials/pages/MaterialListPage').then((m) => ({
    default: m.MaterialListPage,
  })),
);
const MaterialCreatePage = lazy(() =>
  import('./modules/materials/pages/MaterialCreatePage').then((m) => ({
    default: m.MaterialCreatePage,
  })),
);
const MaterialDetailPage = lazy(() =>
  import('./modules/materials/pages/MaterialDetailPage').then((m) => ({
    default: m.MaterialDetailPage,
  })),
);
const MaterialEditPage = lazy(() =>
  import('./modules/materials/pages/MaterialEditPage').then((m) => ({
    default: m.MaterialEditPage,
  })),
);
const EquipmentListPage = lazy(() =>
  import('./modules/equipments/pages/EquipmentListPage').then((m) => ({
    default: m.EquipmentListPage,
  })),
);
const EquipmentCreatePage = lazy(() =>
  import('./modules/equipments/pages/EquipmentCreatePage').then((m) => ({
    default: m.EquipmentCreatePage,
  })),
);
const EquipmentDetailPage = lazy(() =>
  import('./modules/equipments/pages/EquipmentDetailPage').then((m) => ({
    default: m.EquipmentDetailPage,
  })),
);
const EquipmentEditPage = lazy(() =>
  import('./modules/equipments/pages/EquipmentEditPage').then((m) => ({
    default: m.EquipmentEditPage,
  })),
);
// 靶点域 tgt（docs/decisions/2026-08-17-target-domain.md）
const TargetListPage = lazy(() =>
  import('./modules/targets/pages/TargetListPage').then((m) => ({ default: m.TargetListPage })),
);
const TargetCreatePage = lazy(() =>
  import('./modules/targets/pages/TargetCreatePage').then((m) => ({ default: m.TargetCreatePage })),
);
const TargetDetailPage = lazy(() =>
  import('./modules/targets/pages/TargetDetailPage').then((m) => ({ default: m.TargetDetailPage })),
);
const TargetEditPage = lazy(() =>
  import('./modules/targets/pages/TargetEditPage').then((m) => ({ default: m.TargetEditPage })),
);
const UserListPage = lazy(() =>
  import('./modules/admin/pages/UserListPage').then((m) => ({ default: m.UserListPage })),
);
const RoleListPage = lazy(() =>
  import('./modules/admin/pages/RoleListPage').then((m) => ({ default: m.RoleListPage })),
);
const PermissionListPage = lazy(() =>
  import('./modules/admin/pages/PermissionListPage').then((m) => ({
    default: m.PermissionListPage,
  })),
);
const AuditLogPage = lazy(() =>
  import('./modules/admin/pages/AuditLogPage').then((m) => ({ default: m.AuditLogPage })),
);
const SignatureListPage = lazy(() =>
  import('./modules/admin/pages/SignatureListPage').then((m) => ({ default: m.SignatureListPage })),
);
const SessionPolicyPage = lazy(() =>
  import('./modules/admin/pages/SessionPolicyPage').then((m) => ({
    default: m.SessionPolicyPage,
  })),
);
const DeptAdminPolicyPage = lazy(() =>
  import('./modules/admin/pages/DeptAdminPolicyPage').then((m) => ({
    default: m.DeptAdminPolicyPage,
  })),
);
const ProfilePage = lazy(() =>
  import('./modules/profile/pages/ProfilePage').then((m) => ({ default: m.ProfilePage })),
);

const PageFallback = (
  <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 0' }}>
    <Spin size="large" />
  </div>
);

export default function App() {
  // key=路径：换页时错误边界自动复位，不会一处出错后整站一直显示错误卡片
  const location = useLocation();
  return (
    <>
      {/* 必须放在 keyed 边界之外：key 变化会重挂组件，「已知过期→下次换页刷新」就永远不触发 */}
      <AppUpdateWatcher />
      <AppErrorBoundary key={location.pathname}>
        <Suspense fallback={PageFallback}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route element={<ProtectedRoute />}>
              <Route element={<MainLayout />}>
                <Route path="/" element={<HomeRedirect />} />
                <Route path="/dashboard" element={<DashboardPage />} />

                {/* SRS */}
                <Route path="/substances" element={<SubstanceListPage />} />
                <Route path="/substances/new" element={<SubstanceCreatePage />} />
                <Route path="/substances/:code" element={<SubstanceDetailPage />} />
                <Route path="/substances/:code/edit" element={<SubstanceEditPage />} />

                {/* PRS */}
                <Route path="/projects" element={<ProjectListPage />} />
                <Route path="/projects/new" element={<ProjectCreatePage />} />
                <Route path="/projects/:code" element={<ProjectDetailPage />} />
                  <Route path="/pm-projects/:pmProjectId" element={<PMProjectContextPage />} />
                <Route path="/projects/:code/edit" element={<ProjectEditPage />} />

                {/* ARS */}
                <Route path="/assets" element={<AssetListPage />} />
                <Route path="/assets/new" element={<AssetCreatePage />} />
                <Route path="/assets/:code" element={<AssetDetailPage />} />
                <Route path="/assets/:code/edit" element={<AssetEditPage />} />

                {/* MM (Phase 4.A) */}
                <Route path="/materials" element={<MaterialListPage />} />
                <Route path="/materials/new" element={<MaterialCreatePage />} />
                <Route path="/materials/:code" element={<MaterialDetailPage />} />
                <Route path="/materials/:code/edit" element={<MaterialEditPage />} />

                {/* EQP 设备主数据域 */}
                <Route path="/equipments" element={<EquipmentListPage />} />
                <Route path="/equipments/new" element={<EquipmentCreatePage />} />
                <Route path="/equipments/:code" element={<EquipmentDetailPage />} />
                <Route path="/equipments/:code/edit" element={<EquipmentEditPage />} />

                {/* 靶点域 tgt */}
                <Route path="/targets" element={<TargetListPage />} />
                <Route path="/targets/new" element={<TargetCreatePage />} />
                <Route path="/targets/:code" element={<TargetDetailPage />} />
                <Route path="/targets/:code/edit" element={<TargetEditPage />} />

                {/* 系统管理（Phase 5.A：M5.1 用户 / M5.2 角色权限 / M5.3 审计签名）*/}
                <Route path="/admin/users" element={<UserListPage />} />
                <Route path="/admin/audit-logs" element={<AuditLogPage />} />
                <Route path="/admin/signatures" element={<SignatureListPage />} />
                {/* 部门管理员（DEPT_ADMIN）只有用户页；下面几页仅全公司范围管理员可进 */}
                <Route element={<FullAdminRoute />}>
                  <Route path="/admin/roles" element={<RoleListPage />} />
                  <Route path="/admin/permissions" element={<PermissionListPage />} />
                  <Route path="/admin/session-policy" element={<SessionPolicyPage />} />
                  <Route path="/admin/dept-admin-policy" element={<DeptAdminPolicyPage />} />
                </Route>
                <Route path="/admin/*" element={<Navigate to="/admin/users" replace />} />

                {/* M5.3 审计页接入后，旧的 /audit/* 兜底重定向到全局审计 */}
                <Route path="/audit/*" element={<Navigate to="/admin/audit-logs" replace />} />
                {/* M5.4 个人中心 */}
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/profile/password" element={<ChangePasswordPage />} />

                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </AppErrorBoundary>
    </>
  );
}
