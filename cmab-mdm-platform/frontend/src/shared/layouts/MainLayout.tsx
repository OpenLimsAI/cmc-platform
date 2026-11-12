import { useEffect, useState } from 'react';
import { Button, Layout, Modal, Typography, theme } from 'antd';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { APP_VERSION } from '@/shared/version';
import { useSessionGuard } from '@/shared/useSessionGuard';
import { useAuthStore } from '@/stores/authStore';

export function MainLayout() {
  const { token } = theme.useToken();
  // 会话守卫：空闲超时自动登出 + 通行证快到期静默续期 + 多标签页同步
  const retrySession = useSessionGuard();
  const unavailable = useAuthStore((s) => s.authMode === 'oidc' && s.oidcVerificationUnavailable);
  // UI1（V1.1 §3.1）：Footer 显示版本号 + 服务器时间（前端每秒刷新）
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    // 外壳钉死在视口高度并禁滚，使 Header / 左侧 Sidebar 固定；只让右侧内容区滚动
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Modal open={unavailable} title="暂时无法确认登录状态" closable={false}
        maskClosable={false} keyboard={false} zIndex={2000}
        footer={<Button onClick={retrySession}>重新检查</Button>}>
        <p>操作已暂停。你填写的内容会保留，连接恢复后会自动重新检查。</p>
      </Modal>
      <Header />
      <Layout style={{ overflow: 'hidden' }}>
        <Sidebar />
        <Layout style={{ overflow: 'hidden' }}>
          <Layout.Content
            style={{
              padding: 22,
              background: token.colorBgLayout,
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
              background: token.colorBgContainer,
              borderTop: `1px solid ${token.colorBorderSecondary}`,
              textAlign: 'center',
              color: token.colorTextSecondary,
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
