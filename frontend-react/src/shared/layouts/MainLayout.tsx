import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Typography, Space, Dropdown } from "antd";
import {
  DashboardOutlined,
  AppstoreOutlined,
  ImportOutlined,
  ExportOutlined,
  DatabaseOutlined,
  AlertOutlined,
  UserOutlined,
  LogoutOutlined,
  SwapOutlined,
  ToolOutlined,
  GoldOutlined,
  FileExcelOutlined,
  AuditOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { useAuthStore } from "../../stores/authStore";
import { logout } from "../../api/auth";

const { Header, Sider, Content } = Layout;

// 物料库存 — 所有人可见(只读;物料新增/编辑在 MDM Portal)
const materialReadItems = [
  { key: "/materials", icon: <AppstoreOutlined />, label: "物料查询" },
  { key: "/stock", icon: <DatabaseOutlined />, label: "库存查询" },
];

// 物料库存 — 仅库管员/管理员可见(写操作,后端 require_warehouse)
const materialWriteItems = [
  { key: "/import", icon: <FileExcelOutlined />, label: "物料导入" },
  { key: "/intake", icon: <ImportOutlined />, label: "入库登记" },
  { key: "/intake-bulk", icon: <ImportOutlined />, label: "批量入库" },
  { key: "/outgoing", icon: <ExportOutlined />, label: "出库登记" },
  { key: "/transfer", icon: <SwapOutlined />, label: "移库" },
  { key: "/adjust", icon: <ToolOutlined />, label: "盘点调整" },
  { key: "/storage", icon: <GoldOutlined />, label: "位置管理" },
];

// 仪器设备 — 所有人可见(列表只读;新增/编辑按角色控制在页面内)
const equipmentItems = [
  { key: "/equipment", icon: <ExperimentOutlined />, label: "设备台账" },
];

// 预警中心(物料 + 设备聚合)
const alertItems = [
  { key: "/alerts", icon: <AlertOutlined />, label: "预警中心" },
];

// 系统管理 — 用户管理已移至 MDM Portal,此处仅保留审计日志
const adminItems = [
  { key: "/admin/audit", icon: <AuditOutlined />, label: "审计日志" },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, clearAuth, hasRole, canWrite } = useAuthStore();

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      clearAuth();
      navigate("/login");
    }
  };

  // FR-PLT-002: 导航按模块分组;FR-PLT-003: 无权限的入口自动隐藏
  const items = [
    { key: "/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
    {
      key: "grp-material",
      label: "物料库存",
      type: "group" as const,
      children: [
        ...materialReadItems,
        ...(canWrite() ? materialWriteItems : []),
      ],
    },
    {
      key: "grp-equipment",
      label: "仪器设备",
      type: "group" as const,
      children: equipmentItems,
    },
    {
      key: "grp-alerts",
      label: "预警",
      type: "group" as const,
      children: alertItems,
    },
    ...(hasRole("SYS_ADMIN")
      ? [{
          key: "grp-admin",
          label: "系统管理",
          type: "group" as const,
          children: adminItems,
        }]
      : []),
  ];

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
            {collapsed ? "CMC" : "CMC LabOps Portal"}
          </Typography.Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[
            // 详情页(如 /equipment/3)高亮对应列表菜单
            location.pathname.startsWith("/equipment")
              ? "/equipment"
              : location.pathname,
          ]}
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
