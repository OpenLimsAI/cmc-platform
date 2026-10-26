import { useRef } from 'react';
import { Alert, Button, Descriptions, Form, Input, Select, Space, Spin, Typography } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { pmCreateApi, type PMCreateProject, type PMCreateState } from '@/api/pmCreate';
import { oidcLoginPath } from '@/api/oidc';
import { useAuthStore } from '@/stores/authStore';
import { stableCreateRequestId } from '@/shared/oidcPolicy';

const STATUS = {
  pending: '请求已保存，尚未确认执行结果', in_progress: '正在核对或创建，请勿重复发起',
  retryable_error: '结果尚未完成，可沿用同一请求核对并重试', remote_created: 'PM 已创建，正在完成本地关联',
  linked: '创建及一对一关联已完成', reconciliation_required: '两端结果存在冲突，需要人工对账；不会自动改绑或删除',
};
const ERROR = { pm_unavailable: 'PM 暂不可用或响应结果不明', pm_permission_denied: '当前委托用户没有所需 PM 权限',
  pm_conflict: 'PM 项目编号或创建请求存在冲突', local_link_conflict: 'MDM 关联已发生冲突',
  pm_input_rejected: 'PM 明确拒绝创建输入。请核对业务字段并由有权限人员处理原请求，不会隐式改参或另建项目。',
};

export function ProjectPMCreateForm({ projectCode }: { projectCode: string }) {
  const mode = useAuthStore((s) => s.authMode);
  const delegated = useAuthStore((s) => s.pmDelegated);
  const cache = useQueryClient();
  const requestId = useRef<string | null>(null);
  const [form] = Form.useForm<PMCreateProject & { change_reason: string }>();
  const key = ['project-pm-create', projectCode];
  const operation = useQuery({ queryKey: key, queryFn: () => pmCreateApi.get(projectCode), retry: false,
    refetchInterval: (query) => ['pending', 'in_progress', 'remote_created'].includes(query.state.data?.operation?.status ?? '') ? 2500 : false,
  });
  const owners = useQuery({ queryKey: ['pm-create-owner-options'], queryFn: pmCreateApi.owners, retry: false,
    enabled: mode === 'oidc' && delegated && operation.data?.operation === null,
  });
  const done = (data: PMCreateState) => {
    cache.setQueryData(key, data);
    if (data.operation?.status === 'linked') void cache.invalidateQueries({ queryKey: ['project-pm-link', projectCode] });
  };
  const create = useMutation({ mutationFn: (values: PMCreateProject & { change_reason: string }) => {
    requestId.current = stableCreateRequestId(operation.data?.operation?.request_id ?? null, requestId.current, () => crypto.randomUUID());
    const { change_reason, ...project } = values;
    return pmCreateApi.create(projectCode, { client_request_id: requestId.current, change_reason, project });
  }, onSuccess: done, onError: () => { void operation.refetch(); } });
  const retry = useMutation({ mutationFn: () => pmCreateApi.retry(projectCode), onSuccess: done, onError: () => { void operation.refetch(); } });
  const context = `/projects/${encodeURIComponent(projectCode)}`;
  if (mode !== 'oidc') return <Alert type="info" message="创建 PM 执行项目需要统一身份登录和明确的 PM 用户授权" description="原生登录仍可按既有配置关联已有项目；不会用静态核验身份代替创建权限。" />;
  if (!delegated) return <Alert type="info" message="先授权当前用户调用 PM 项目接口" description="将通过 Casdoor 标准授权流程核实同一用户的 PM 权限，不会把 MDM 登录令牌传给 PM。授权成功后仍需您明确提交创建。" action={<Button href={oidcLoginPath(context, true)}>授权 PM 项目操作</Button>} />;
  if (operation.isPending) return <Spin />;
  if (!operation.data) return <Alert type="error" message="无法确认已有创建请求，暂停发起新请求" description="请先核对服务状态；重复提交不会被当作一次新的创建。" action={<Button onClick={() => { void operation.refetch(); }}>查询已有请求</Button>} />;
  const saved = operation.data.operation;
  if (saved) return <Space direction="vertical" style={{ width: '100%' }}>
    <Alert type={saved.status === 'linked' ? 'success' : saved.status === 'reconciliation_required' ? 'error' : 'warning'} showIcon message={saved.last_error === 'pm_input_rejected' ? ERROR.pm_input_rejected : STATUS[saved.status]} />
    <Descriptions column={1} bordered items={[
      { key: 'request', label: '创建请求 ID', children: saved.request_id },
      { key: 'target', label: '请求中的 PM 项目', children: `${saved.project.code} · ${saved.project.name}` },
      { key: 'attempts', label: '已执行尝试', children: saved.attempts },
      { key: 'remote', label: '已确认 PM 项目 ID', children: saved.remote_project_id ?? '尚未确认' },
      { key: 'error', label: '当前结果', children: saved.last_error ? ERROR[saved.last_error as keyof typeof ERROR] ?? '请核对请求状态后处理' : STATUS[saved.status] },
    ]} />
    <Space wrap><Button onClick={() => { void operation.refetch(); }} loading={operation.isFetching}>核对当前结果</Button>
      {saved.last_error === 'pm_permission_denied' && <Button href={oidcLoginPath(context, true)}>重新核验 PM 授权</Button>}
      {saved.can_retry && <Button onClick={() => retry.mutate()} loading={retry.isPending}>沿用同一请求重试</Button>}
      {saved.status === 'linked' && saved.pm_url && <Button href={saved.pm_url} target="_blank" rel="noopener noreferrer">打开已创建 PM 项目</Button>}
    </Space>
    {retry.isError && <Alert type="warning" message="本次重试尚未确认成功，请查询原请求；不会另建请求。" />}
  </Space>;
  if (owners.isPending) return <Spin />;
  if (!owners.data) return <Alert type="error" message="无法读取当前 PM 用户可用的负责人和阶段选项" description="请确认 PM 创建权限与用户委托，再重试。" action={<Space><Button onClick={() => { void owners.refetch(); }}>重试</Button><Button href={oidcLoginPath(context, true)}>重新核验 PM 授权</Button></Space>} />;
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Typography.Paragraph>明确填写 PM 执行项目后创建，并与此登记项目建立一对一关联。PM 决定创建权限和字段有效性；不会复制 MDM 阶段、预算或团队。</Typography.Paragraph>
    <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)}>
      <Form.Item name="code" label="PM 项目编号" rules={[{ required: true }, { max: 40 }]}><Input autoComplete="off" /></Form.Item>
      <Form.Item name="name" label="PM 项目名称" rules={[{ required: true }, { max: 200 }]}><Input autoComplete="off" /></Form.Item>
      <Form.Item name="product_type" label="PM 产品类型" rules={[{ required: true }]}><Select placeholder="明确选择产品类型" options={owners.data.options.product_types.map((value) => ({ value, label: value }))} /></Form.Item>
      <Form.Item name="current_stage" label="PM 当前执行阶段" rules={[{ required: true }]}><Select placeholder="明确选择当前阶段" options={owners.data.options.stages.map((value) => ({ value, label: value }))} /></Form.Item>
      <Form.Item name="target_stage" label="PM 目标阶段" rules={[{ required: true }]}><Select placeholder="明确选择目标阶段" options={owners.data.options.stages.map((value) => ({ value, label: value }))} /></Form.Item>
      <Form.Item name="owner_id" label="PM 执行负责人" rules={[{ required: true }]}><Select placeholder="从 PM 权威候选中明确选择" options={owners.data.items.map((item) => ({ value: item.id, label: item.display_name }))} /></Form.Item>
      <Form.Item name="planned_start" label="PM 计划开始日期" rules={[{ required: true }]}><Input type="date" /></Form.Item>
      <Form.Item name="planned_end" label="PM 计划结束日期" dependencies={['planned_start']} rules={[{ required: true }, { validator: (_, value) => !value || !form.getFieldValue('planned_start') || value >= form.getFieldValue('planned_start') ? Promise.resolve() : Promise.reject(new Error('结束日期不得早于开始日期')) }]}><Input type="date" /></Form.Item>
      <Form.Item name="description" label="PM 项目说明（可选）"><Input.TextArea maxLength={5000} /></Form.Item>
      <Form.Item name="change_reason" label="创建并关联的原因" rules={[{ required: true }, { min: 5, max: 1000 }]}><Input.TextArea /></Form.Item>
      {create.isError && <Alert type="warning" showIcon message="未确认创建及关联完成" description="正在核对同一请求状态。请勿改用另一编号重复创建；待查询后沿用原请求重试。" style={{ marginBottom: 16 }} />}
      <Button htmlType="submit" type="primary" loading={create.isPending} disabled={operation.isFetching}>创建 PM 执行项目并关联</Button>
    </Form>
  </Space>;
}
