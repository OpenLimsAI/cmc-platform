import { useEffect, useState } from 'react';
import { Layout, Typography } from 'antd';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { APP_VERSION } from '@/shared/version';

export function MainLayout() {
  // UI1（V1.1 §3.1）：Footer 显示版本号 + 服务器时间（前端每秒刷新）
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header />
      <Layout>
        <Sidebar />
        <Layout>
          <Layout.Content
            style={{
              padding: 24,
              background: '#f5f5f5',
              minHeight: 'calc(100vh - 56px - 32px)', // 减 header 高 + footer 高
            }}
          >
            <Outlet />
          </Layout.Content>
          <Layout.Footer
            style={{
              padding: '6px 24px',
              fontSize: 12,
              background: '#fafafa',
              borderTop: '1px solid #f0f0f0',
              textAlign: 'center',
              color: '#8c8c8c',
            }}
          >
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              CMAB MDM Portal · {APP_VERSION} · {now.toLocaleString('zh-CN', { hour12: false })}
            </Typography.Text>
          </Layout.Footer>
        </Layout>
      </Layout>
    </Layout>
  );
}
