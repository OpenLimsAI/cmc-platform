import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

import MainLayout from "./shared/layouts/MainLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import LoginPage from "./modules/admin/pages/LoginPage";
import MaterialListPage from "./modules/materials/pages/MaterialListPage";
import IntakePage from "./modules/intake/pages/IntakePage";
import OutgoingPage from "./modules/outgoing/pages/OutgoingPage";
import StockPage from "./modules/stock/pages/StockPage";
import AlertsPage from "./modules/alerts/pages/AlertsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>
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
              <Route path="/materials" element={<MaterialListPage />} />
              <Route path="/intake" element={<IntakePage />} />
              <Route path="/outgoing" element={<OutgoingPage />} />
              <Route path="/stock" element={<StockPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/materials" replace />} />
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
