import { Layout, Avatar, Dropdown, Space, message, theme, Modal, Tag } from 'antd';
import { UserOutlined, LogoutOutlined, KeyOutlined, BellOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { authApi } from '@/api/auth';
import { GlobalSearchBox } from '@/shared/components/GlobalSearchBox';
import { oidcApi } from '@/api/oidc';
import { completeOidcLogout } from '@/shared/oidcPolicy';
import { withBase } from '@/shared/base';

const { Header: AntHeader } = Layout;

export function Header() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const authMode = useAuthStore((s) => s.authMode);
  const { token } = theme.useToken();

  const handleLogout = async (global = false) => {
    const intentEpoch = useAuthStore.getState().beginLogout();
    if (authMode === 'oidc') {
      try {
        const result = await oidcApi.logout(global);
        if (useAuthStore.getState().authEpoch !== intentEpoch) return;
        const handled = completeOidcLogout(result, global, new URL(withBase('/login?reason=logout'), window.location.origin).href, {
          clearLocal: () => logout('logout'),
          navigateLocal: () => navigate('/login?reason=logout'),
          navigateProvider: (url) => window.location.assign(url),
          warn: (text, acknowledge) => { Modal.warning({ title: global ? '统一身份注销结果提示' : '注销结果提示', content: text, keyboard: false, maskClosable: false, okText: '已知晓，继续退出', onOk: () => { if (useAuthStore.getState().authEpoch === intentEpoch) acknowledge(); } }); },
        });
        if (!handled) { useAuthStore.getState().cancelLogout(intentEpoch); message.error('无法确认 MDM 服务端注销，请重试。'); }
      } catch {
        useAuthStore.getState().cancelLogout(intentEpoch);
        message.error('无法确认服务端注销，请重试。不会把清除前端状态视为统一退出。');
      }
      return;
    }
    try {
      await authApi.logout();
    } catch {
      // 即使后端报错也要本地登出
    }
    if (useAuthStore.getState().authEpoch !== intentEpoch) return;
    logout('logout');
    navigate('/login?reason=logout');
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
        label: authMode === 'oidc' ? '仅退出 MDM' : '退出登录',
        onClick: () => { void handleLogout(); },
      },
      ...(authMode === 'oidc' ? [{ key: 'logout-global', icon: <LogoutOutlined />, label: '退出统一身份及各应用',
        onClick: () => Modal.confirm({ title: '退出统一身份及已接入应用', content: '将注销 Casdoor，并通过受验证的回调令 MDM、PM、门户会话失效。原生密码登录和未接入应用不属于此统一注销范围。', okText: '统一退出', cancelText: '取消', onOk: () => handleLogout(true) }) }] : []),
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
        <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="CMAB MDM" style={{ width: 32, height: 32, display: 'block' }} />
        <div style={{ fontSize: 18, fontWeight: 600, color: token.colorPrimary }}>
          CMAB MDM Portal
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <GlobalSearchBox />
      </div>

      <Space size="large">
        <BellOutlined style={{ fontSize: 18, color: token.colorTextSecondary, cursor: 'pointer' }} />
        <Tag>{authMode === 'oidc' ? 'Casdoor 登录' : '原生登录'}</Tag>
        <Dropdown menu={userMenu} placement="bottomRight" trigger={['click']}>
          <Space style={{ cursor: 'pointer' }}>
            <Avatar size="small" icon={<UserOutlined />} style={{ background: token.colorPrimary }} />
            <span style={{ color: token.colorText }}>{user?.full_name || user?.username}</span>
          </Space>
        </Dropdown>
      </Space>
    </AntHeader>
  );
}
