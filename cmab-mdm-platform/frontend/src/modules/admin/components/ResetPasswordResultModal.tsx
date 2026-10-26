import { Modal, Alert, Input, Button, Typography, message } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import type { ResetPasswordResult } from '@/api/types';

const { Text } = Typography;

interface Props {
  open: boolean;
  result: ResetPasswordResult | null;
  onClose: () => void;
}

export function ResetPasswordResultModal({ open, result, onClose }: Props) {
  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.temp_password);
      message.success('临时密码已复制到剪贴板');
    } catch {
      message.error('复制失败，请手动选择文本复制');
    }
  };

  return (
    <Modal
      title={`重置密码完成 — ${result?.username ?? ''}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="copy" icon={<CopyOutlined />} onClick={copy} disabled={!result}>
          复制临时密码
        </Button>,
        <Button key="ok" type="primary" onClick={onClose}>
          我已记下
        </Button>,
      ]}
      width={520}
    >
      <Alert
        type="warning"
        showIcon
        message="临时密码仅本次显示一次"
        description="关闭此窗口后无法再次查看。请通过安全渠道（当面 / 加密 IM）告知用户，并提醒首次登录后立即修改。"
        style={{ marginBottom: 16 }}
      />
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">用户首次登录时会被强制跳转到改密页（force_password_change=TRUE）。</Text>
      </div>
      <Input.Password
        value={result?.temp_password ?? ''}
        readOnly
        size="large"
        addonBefore="临时密码"
        visibilityToggle
      />
    </Modal>
  );
}
