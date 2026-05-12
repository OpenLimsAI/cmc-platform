import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, Space, message } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';

const { TextArea } = Input;

export interface StatusActionDef {
  /** 后端状态机 action（冒号端点动词，如 'approve', 'start'）*/
  action: string;
  /** 中文按钮文案 */
  label: string;
  /** 高风险动作（红色按钮 + 危险确认）*/
  danger?: boolean;
  /** GxP 关键动作：弹窗需输入密码做电子签名（21 CFR Part 11 §11.200）*/
  requiresSignature?: boolean;
}

interface Props<TDetail extends { status: string }> {
  /** 当前 status 下可执行的动作列表（按 status 查表后传入；空数组时整组不渲染）*/
  actions: StatusActionDef[];
  /** 调用后端冒号端点的函数；签名场景多传 password 字段 */
  changeStatusFn: (action: string, change_reason: string, password?: string) => Promise<TDetail>;
  /** 触发动作所需权限码（如 'project:approve'）*/
  permission: string;
  /** 用于 invalidate 缓存的 queryKey（详情）*/
  detailQueryKey: readonly unknown[];
  /** 用于 invalidate 缓存的 queryKey（列表前缀）*/
  listQueryKey: readonly unknown[];
  /** 实体编码（弹窗标题用）*/
  entityCode: string;
  /** 实体类型中文（如 "项目"，"物质"）用于警告文案 */
  entityTypeLabel?: string;
}

/**
 * 通用状态机按钮组 + 变更原因弹窗。SRS/PRS/未来 ARS/MM 共用。
 */
export function StatusActionsBar<TDetail extends { status: string }>({
  actions,
  changeStatusFn,
  permission,
  detailQueryKey,
  listQueryKey,
  entityCode,
  entityTypeLabel = '对象',
}: Props<TDetail>) {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<StatusActionDef | null>(null);
  const [form] = Form.useForm<{ change_reason: string; password?: string }>();

  const canTrigger = hasPermission(permission);

  const mutation = useMutation({
    mutationFn: ({
      action,
      reason,
      password,
    }: {
      action: string;
      reason: string;
      password?: string;
    }) => changeStatusFn(action, reason, password),
    onSuccess: (data, vars) => {
      const def = actions.find((a) => a.action === vars.action);
      message.success(`已${def?.label ?? vars.action}：状态变为 ${data.status}`);
      queryClient.invalidateQueries({ queryKey: detailQueryKey });
      queryClient.invalidateQueries({ queryKey: listQueryKey });
      setPending(null);
      form.resetFields();
    },
    onError: (err: any) => {
      const status = err?.response?.status;
      const errType = err?.response?.data?.meta?.error?.type;
      if (status === 401 && errType === 'signature_invalid') {
        message.error('电子签名失败：密码错误');
      } else if (status === 422 && errType === 'signature_required') {
        message.error('此操作必须电子签名，请输入密码');
      } else {
        message.error(err?.response?.data?.message ?? '状态变更失败');
      }
    },
  });

  if (actions.length === 0) return null;

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (!pending) return;
    mutation.mutate({
      action: pending.action,
      reason: values.change_reason,
      password: pending.requiresSignature ? values.password : undefined,
    });
  };

  return (
    <>
      <Space>
        {actions.map((def) => (
          <Button
            key={def.action}
            danger={def.danger}
            disabled={!canTrigger}
            onClick={() => setPending(def)}
            title={canTrigger ? undefined : `需要 ${permission} 权限`}
          >
            {def.label}
          </Button>
        ))}
      </Space>

      <Modal
        open={pending !== null}
        title={
          pending
            ? `${pending.label}${pending.requiresSignature ? ' · 电子签名' : ''} - ${entityCode}`
            : ''
        }
        onCancel={() => {
          setPending(null);
          form.resetFields();
        }}
        onOk={handleSubmit}
        confirmLoading={mutation.isPending}
        okText={pending?.requiresSignature ? '签名并提交' : '确认提交'}
        cancelText="取消"
        okButtonProps={{ danger: pending?.danger }}
        destroyOnClose
      >
        <Alert
          type={pending?.requiresSignature ? 'info' : 'warning'}
          showIcon
          message={
            pending?.requiresSignature
              ? `此为 GxP 关键动作，将以电子签名形式记录（21 CFR Part 11 §11.50）。提交即等同手写签名，无法撤销。`
              : `此操作将变更${entityTypeLabel}状态并写入审计日志，无法撤销。请填写变更原因。`
          }
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="change_reason"
            label="变更原因（最少 5 字）"
            rules={[
              { required: true, message: '必须填写变更原因' },
              { min: 5, message: '原因至少 5 字' },
              { max: 2000 },
            ]}
          >
            <TextArea rows={4} placeholder="说明此次状态变更的业务依据" />
          </Form.Item>
          {pending?.requiresSignature && (
            <Form.Item
              name="password"
              label="登录密码"
              tooltip="重新输入当前登录密码以完成电子签名（21 CFR Part 11 §11.200）"
              rules={[{ required: true, message: '必须输入密码完成签名' }]}
            >
              <Input.Password placeholder="重新输入您的登录密码" autoComplete="off" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </>
  );
}
