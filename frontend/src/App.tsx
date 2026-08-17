import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import HubPage from '@/pages/HubPage'
import LoginPage from '@/pages/LoginPage'
import { isTokenExpired, useAuth } from '@/stores/authStore'

// 门禁：未登录 / 令牌过期一律回登录页（带 redirect 回跳）
function RequireAuth() {
  const { token } = useAuth()
  const loc = useLocation()
  if (!token || isTokenExpired(token)) {
    const redirect = encodeURIComponent(loc.pathname + loc.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }
  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HubPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
