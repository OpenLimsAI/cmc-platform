import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, Space, message } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import type { SignatureBlock } from '@/api/types';

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

interface Props {
  /** 当前 status 下可执行的动作列表（按 status 查表后传入；空数组时整组不渲染）*/
  actions: StatusActionDef[];
  /** 调用后端冒号端点的函数；payload = { comment, signature?: {password, reason, meaning?} }
   *  对齐 API-MDM-001 V1.1 §6.5 / §7.4 / §8.x；返回 StateChangeResponse（含 new_status）*/
  changeStatusFn: (
    action: string,
    comment: string,
    signature?: SignatureBlock,
  ) => Promise<{ new_status: string }>;
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
export function StatusActionsBar({
  actions,
  changeStatusFn,
  permission,
  detailQueryKey,
  listQueryKey,
  entityCode,
  entityTypeLabel = '对象',
}: Props) {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const oidc = useAuthStore((s) => s.authMode === 'oidc');
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<StatusActionDef | null>(null);
  const [form] = Form.useForm<{
    comment: string;
    password?: string;
    signature_reason?: string;
  }>();

  const canTrigger = hasPermission(permission);

  const mutation = useMutation({
    mutationFn: ({
      action,
      comment,
      signature,
    }: {
      action: string;
      comment: string;
      signature?: SignatureBlock;
    }) => changeStatusFn(action, comment, signature),
    onSuccess: (data, vars) => {
      const def = actions.find((a) => a.action === vars.action);
      message.success(`已${def?.label ?? vars.action}：状态变为 ${data.new_status}`);
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

  const submit = (values: {
    comment: string;
    password?: string;
    signature_reason?: string;
  }) => {
    if (!pending) return;
    const signature =
      pending.requiresSignature && values.password && values.signature_reason
        ? { password: values.password, reason: values.signature_reason }
        : undefined;
    mutation.mutate({
      action: pending.action,
      comment: values.comment,
      signature,
    });
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    // UI4：GxP 关键动作（不可逆 / 需电子签名）提交前再做一次二次确认
    // V1.1 §7.3 / §9.2.1 / 21 CFR Part 11 §11.50 要求
    if (pending?.requiresSignature || pending?.danger) {
      Modal.confirm({
        title: `确认执行：${pending.label}`,
        content: (
          <div>
            <p>该操作不可撤销，将以电子签名形式记录。</p>
            <p style={{ color: '#cf1322', marginBottom: 0 }}>
              点击「确认签名」后立即生效，本次操作将永久写入审计日志。
            </p>
          </div>
        ),
        okText: '确认签名',
        okType: 'danger',
        cancelText: '我再想想',
        centered: true,
        onOk: () => submit(values),
      });
    } else {
      submit(values);
    }
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
            name="comment"
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
            <>
              <Form.Item
                name="signature_reason"
                label="签名理由（最少 5 字）"
                tooltip="独立于变更原因记录的签名含义说明（21 CFR Part 11 §11.50）"
                rules={[
                  { required: true, message: '必须填写签名理由' },
                  { min: 5, message: '签名理由至少 5 字' },
                  { max: 2000 },
                ]}
              >
                <TextArea rows={2} placeholder="如：Phase I 数据评审通过 / 批文已签发 / 合规终止" />
              </Form.Item>
              <Form.Item
                name="password"
                label={oidc ? 'MDM 签名密码（非 Casdoor 密码）' : '登录密码'}
                tooltip={oidc ? 'SSO 不替代签名再次认证；请输入此数字用户原有的 MDM 密码。' : '重新输入当前登录密码以完成电子签名（21 CFR Part 11 §11.200）'}
                rules={[{ required: true, message: '必须输入密码完成签名' }]}
              >
                <Input.Password placeholder={oidc ? '重新输入 MDM 签名密码' : '重新输入您的登录密码'} autoComplete="off" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </>
  );
}
