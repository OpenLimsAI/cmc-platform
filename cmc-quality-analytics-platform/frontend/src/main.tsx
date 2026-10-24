import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { BASE } from './shared/base'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <BrowserRouter basename={BASE}>
        <AuthProvider><App /></AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
)
