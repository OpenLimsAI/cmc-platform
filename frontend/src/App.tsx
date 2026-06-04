import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './modules/auth/pages/LoginPage';
import { DashboardPage } from './modules/dashboard/pages/DashboardPage';
import { SubstanceListPage } from './modules/substances/pages/SubstanceListPage';
import { SubstanceCreatePage } from './modules/substances/pages/SubstanceCreatePage';
import { SubstanceDetailPage } from './modules/substances/pages/SubstanceDetailPage';
import { SubstanceEditPage } from './modules/substances/pages/SubstanceEditPage';
import { ChangePasswordPage } from './modules/auth/pages/ChangePasswordPage';
import { ProjectListPage } from './modules/projects/pages/ProjectListPage';
import { ProjectCreatePage } from './modules/projects/pages/ProjectCreatePage';
import { ProjectDetailPage } from './modules/projects/pages/ProjectDetailPage';
import { ProjectEditPage } from './modules/projects/pages/ProjectEditPage';
import { AssetListPage } from './modules/assets/pages/AssetListPage';
import { AssetCreatePage } from './modules/assets/pages/AssetCreatePage';
import { AssetDetailPage } from './modules/assets/pages/AssetDetailPage';
import { AssetEditPage } from './modules/assets/pages/AssetEditPage';
import { MaterialListPage } from './modules/materials/pages/MaterialListPage';
import { EquipmentListPage } from './modules/equipments/pages/EquipmentListPage';
import { EquipmentCreatePage } from './modules/equipments/pages/EquipmentCreatePage';
import { EquipmentDetailPage } from './modules/equipments/pages/EquipmentDetailPage';
import { EquipmentEditPage } from './modules/equipments/pages/EquipmentEditPage';
import { MaterialCreatePage } from './modules/materials/pages/MaterialCreatePage';
import { MaterialDetailPage } from './modules/materials/pages/MaterialDetailPage';
import { MaterialEditPage } from './modules/materials/pages/MaterialEditPage';
import { UserListPage } from './modules/admin/pages/UserListPage';
import { RoleListPage } from './modules/admin/pages/RoleListPage';
import { PermissionListPage } from './modules/admin/pages/PermissionListPage';
import { AuditLogPage } from './modules/admin/pages/AuditLogPage';
import { SignatureListPage } from './modules/admin/pages/SignatureListPage';
import { ProfilePage } from './modules/profile/pages/ProfilePage';
import { NotFoundPage } from './modules/common/NotFoundPage';
import { MainLayout } from './shared/layouts/MainLayout';
import { ProtectedRoute } from './routes/ProtectedRoute';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
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

          {/* 系统管理（Phase 5.A：M5.1 用户 / M5.2 角色权限 / M5.3 审计签名）*/}
          <Route path="/admin/users" element={<UserListPage />} />
          <Route path="/admin/roles" element={<RoleListPage />} />
          <Route path="/admin/permissions" element={<PermissionListPage />} />
          <Route path="/admin/audit-logs" element={<AuditLogPage />} />
          <Route path="/admin/signatures" element={<SignatureListPage />} />
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
  );
}
