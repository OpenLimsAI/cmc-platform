import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Typography, Space, Dropdown } from "antd";
import {
  AppstoreOutlined,
  ImportOutlined,
  ExportOutlined,
  DatabaseOutlined,
  AlertOutlined,
  UserOutlined,
  LogoutOutlined,
  SwapOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { useAuthStore } from "../../stores/authStore";
import { logout } from "../../api/auth";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/materials", icon: <AppstoreOutlined />, label: "物料管理" },
  { key: "/intake", icon: <ImportOutlined />, label: "入库登记" },
  { key: "/outgoing", icon: <ExportOutlined />, label: "出库登记" },
  { key: "/stock", icon: <DatabaseOutlined />, label: "库存查询" },
  { key: "/alerts", icon: <AlertOutlined />, label: "库存预警" },
  { key: "/transfer", icon: <SwapOutlined />, label: "移库" },
  { key: "/adjust", icon: <ToolOutlined />, label: "盘点调整" },
];

const adminItems = [
  { key: "/admin/users", icon: <UserOutlined />, label: "用户管理" },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, clearAuth, hasRole } = useAuthStore();

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      clearAuth();
      navigate("/login");
    }
  };

  const items = hasRole("SYS_ADMIN")
      ? [...menuItems, ...adminItems]
      : menuItems;

  return (
    <Layout style={{ minHeight: "1000px" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme          ='light'
        style={{ borderRight: "1px solid #f0f0f0" }}
      >
        <div style={{ height: 48, margin: 16, textAlign: "center" }}>
          <Typography.Title level={5} style={{ margin: 0, lineHeight: "48px" }}>
            {collapsed ? "CMC" : "CMC 物料管理"}
          </Typography.Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Space>
            <Dropdown
              menu={{
                items: [
                  { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: handleLogout },
                ],
              }}
            >
              <Button type="text" icon={<UserOutlined />}>
                {user?.username}
              </Button>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
