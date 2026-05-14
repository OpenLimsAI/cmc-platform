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
import { MaterialCreatePage } from './modules/materials/pages/MaterialCreatePage';
import { MaterialDetailPage } from './modules/materials/pages/MaterialDetailPage';
import { MaterialEditPage } from './modules/materials/pages/MaterialEditPage';
import { NotFoundPage } from './modules/common/NotFoundPage';
import { PlaceholderPage } from './modules/common/PlaceholderPage';
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

          {/* 占位 - 后续 Phase 实现 */}
          <Route path="/audit/*" element={<PlaceholderPage title="审计模块" />} />
          <Route path="/admin/*" element={<PlaceholderPage title="系统管理" />} />
          <Route path="/profile" element={<PlaceholderPage title="个人中心" />} />
          <Route path="/profile/password" element={<ChangePasswordPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
