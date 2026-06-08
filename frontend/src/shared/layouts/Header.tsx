import { Layout, Avatar, Dropdown, Space, message, theme } from 'antd';
import { UserOutlined, LogoutOutlined, KeyOutlined, BellOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { authApi } from '@/api/auth';
import { GlobalSearchBox } from '@/shared/components/GlobalSearchBox';

const { Header: AntHeader } = Layout;

export function Header() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // 即使后端报错也要本地登出
    }
    logout();
    navigate('/login');
  };

  // V1.1 §3.2.3：用户菜单四项（个人中心 / 偏好设置 / 修改密码 / 退出）
  const userMenu = {
    items: [
      {
        key: 'profile',
        icon: <UserOutlined />,
        label: '个人中心',
        onClick: () => navigate('/profile'),
      },
      {
        key: 'preferences',
        icon: <SettingOutlined />,
        label: '偏好设置',
        // UI2：Phase 4-5 个人偏好（主题/语言/时区）页未实现，先占位
        onClick: () => message.info('偏好设置（Phase 4-5 后实现）'),
      },
      {
        key: 'change-pwd',
        icon: <KeyOutlined />,
        label: '修改密码',
        onClick: () => navigate('/profile/password'),
      },
      { type: 'divider' as const },
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: handleLogout,
      },
    ],
  };

  return (
    <AntHeader
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        height: 56,
        lineHeight: '56px',
        padding: '0 24px',
        background: '#fff',
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* 与浏览器标签页 favicon 同源，保持品牌一致 */}
        <img src="/favicon.svg" alt="CMAB MDM" style={{ width: 32, height: 32, display: 'block' }} />
        <div style={{ fontSize: 18, fontWeight: 600, color: token.colorPrimary }}>
          CMAB MDM Portal
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <GlobalSearchBox />
      </div>

      <Space size="large">
        <BellOutlined style={{ fontSize: 18, color: token.colorTextSecondary, cursor: 'pointer' }} />
        <Dropdown menu={userMenu} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar size="small" icon={<UserOutlined />} style={{ background: token.colorPrimary }} />
            <span style={{ color: token.colorText }}>{user?.full_name || user?.username}</span>
          </Space>
        </Dropdown>
      </Space>
    </AntHeader>
  );
}
