import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

import MainLayout from "./shared/layouts/MainLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import LoginPage from "./modules/admin/pages/LoginPage";
import DashboardPage from "./modules/dashboard/pages/DashboardPage";
import MaterialListPage from "./modules/materials/pages/MaterialListPage";
import IntakePage from "./modules/intake/pages/IntakePage";
import OutgoingPage from "./modules/outgoing/pages/OutgoingPage";
import StockPage from "./modules/stock/pages/StockPage";
import AlertsPage from "./modules/alerts/pages/AlertsPage";
import TransferPage from "./modules/transfer/pages/TransferPage";
import AdjustPage from "./modules/adjust/pages/AdjustPage";
import ImportPage from "./modules/import/pages/ImportPage";
import StoragePage from "./modules/storage/pages/StoragePage";
import AuditLogPage from "./modules/admin/pages/AuditLogPage";
import EquipmentListPage from "./modules/equipment/pages/EquipmentListPage";
import EquipmentDetailPage from "./modules/equipment/pages/EquipmentDetailPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

// 物料写操作页的角色(与后端 require_warehouse 对齐);设备写操作在页面内按钮级控制
const WAREHOUSE_ROLES = ["SYS_ADMIN", "CMC_WAREHOUSE_ADMIN"];

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            // 与 CMAB MDM Portal 视觉规范一致(UI-LABOPS-001 §1.2 色彩系统)
            colorPrimary: "#1F4E79",
            borderRadius: 4,
            // 与 global.css body 的字体栈保持完全一致,避免同一数字在不同组件里字形不一
            fontFamily:
              "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', Roboto, sans-serif",
          },
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/materials" element={<MaterialListPage />} />
              <Route path="/intake" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><IntakePage /></ProtectedRoute>} />
              <Route path="/outgoing" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><OutgoingPage /></ProtectedRoute>} />
              <Route path="/stock" element={<StockPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/transfer" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><TransferPage /></ProtectedRoute>} />
              <Route path="/adjust" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><AdjustPage /></ProtectedRoute>} />
              <Route path="/storage" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><StoragePage /></ProtectedRoute>} />
              <Route path="/import" element={<ProtectedRoute roles={WAREHOUSE_ROLES}><ImportPage /></ProtectedRoute>} />
              <Route path="/equipment" element={<EquipmentListPage />} />
              <Route path="/equipment/:id" element={<EquipmentDetailPage />} />
              <Route path="/admin/audit" element={<ProtectedRoute roles={["SYS_ADMIN"]}><AuditLogPage /></ProtectedRoute>} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
