import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { login } from "../../../api/auth";
import { useAuthStore } from "../../../stores/authStore";
import { getErrorDetail } from "../../../shared/errors";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await login(values);
      setAuth(data.access_token, data.user);

      if (data.user.must_change_password) {
        // 改密在 MDM Portal 操作(V1.1 起本系统无改密页)
        message.warning("MDM 提示需要修改初始密码,请先到 MDM Portal 完成改密", 6);
      }
      navigate("/materials");
    } catch (err: unknown) {
      const detail =
        getErrorDetail(err, "登录失败");
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "#f5f5f5",
      }}
    >
      <Card style={{ width: 400 }}>
        <Typography.Title
          level={3}
          style={{ textAlign: "center", marginBottom: 32 }}
        >
          CMC LabOps Portal
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: "center", marginTop: -24 }}>
          CMC 部门运营平台 · 物料库存 / 仪器设备
        </Typography.Paragraph>
        <Form onFinish={onFinish} size="large">
          <Form.Item
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
