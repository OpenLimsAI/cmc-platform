import { useEffect, useState } from 'react';
import { Layout, Typography } from 'antd';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { APP_VERSION } from '@/shared/version';
import { useSessionGuard } from '@/shared/useSessionGuard';

export function MainLayout() {
  // 会话守卫：空闲超时自动登出 + 通行证快到期静默续期 + 多标签页同步
  useSessionGuard();
  // UI1（V1.1 §3.1）：Footer 显示版本号 + 服务器时间（前端每秒刷新）
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    // 外壳钉死在视口高度并禁滚，使 Header / 左侧 Sidebar 固定；只让右侧内容区滚动
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Header />
      <Layout style={{ overflow: 'hidden' }}>
        <Sidebar />
        <Layout style={{ overflow: 'hidden' }}>
          <Layout.Content
            style={{
              padding: 24,
              background: '#f5f5f5',
              flex: 1,
              overflowY: 'auto', // 仅内容区随滚轮滚动
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
