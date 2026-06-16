import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message, Alert } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { login } from "../../../api/auth";
import { useAuthStore } from "../../../stores/authStore";
import { getErrorDetail } from "../../../shared/errors";

const { Title, Text } = Typography;

/**
 * 登录页 — 视觉与 CMAB MDM Portal 登录页保持一致
 * (渐变背景 #1F4E79→#2E75B6、白色标题、400px 卡片、卡内错误 Alert)。
 * 认证代理 MDM /auth/login,账号/改密在 MDM Portal 维护。
 */
export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const { data } = await login(values);
      setAuth(data.access_token, data.user);

      if (data.user.must_change_password) {
        // 改密在 MDM Portal 操作(V1.1 起本系统无改密页)
        message.warning("MDM 提示需要修改初始密码,请先到 MDM Portal 完成改密", 6);
      }
      navigate("/dashboard");
    } catch (err: unknown) {
      setErrorMessage(getErrorDetail(err, "登录失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%)",
        padding: 24,
      }}
    >
      <div style={{ marginBottom: 40, textAlign: "center" }}>
        <Title level={1} style={{ color: "#fff", marginBottom: 8 }}>
          CMC LabOps Portal
        </Title>
        <Text style={{ color: "rgba(255,255,255,0.85)", fontSize: 16 }}>
          CMC 部门运营平台 · 物料库存 / 仪器设备
        </Text>
      </div>

      <Card style={{ width: 400, boxShadow: "0 8px 32px rgba(0,0,0,0.18)" }}>
        <Title level={3} style={{ marginTop: 0, marginBottom: 24, textAlign: "center" }}>
          工号登录
        </Title>

        {errorMessage && (
          <Alert
            type="error"
            message={errorMessage}
            showIcon
            style={{ marginBottom: 16 }}
            closable
            onClose={() => setErrorMessage(null)}
          />
        )}

        <Form name="login" onFinish={onFinish} autoComplete="off" size="large" layout="vertical">
          <Form.Item
            name="username"
            label="工号"
            rules={[{ required: true, message: "请输入工号" }]}
          >
            <Input prefix={<UserOutlined />} placeholder="工号" autoFocus />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登 录
            </Button>
          </Form.Item>

          <div style={{ textAlign: "center", color: "#8c8c8c", fontSize: 13 }}>
            工号与密码统一在 MDM Portal 维护,忘记密码请联系系统管理员
          </div>
        </Form>
      </Card>

      <div style={{ marginTop: 32, color: "rgba(255,255,255,0.7)", fontSize: 12 }}>
        © 2026 CMAB · CMC LabOps Portal · 内部系统
      </div>
    </div>
  );
}
