import { Alert, Button, Descriptions, Form, Input, Space, Spin, Typography, Tabs } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { pmLinksApi } from '@/api/pmLinks';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { ProjectPMCreateForm } from './ProjectPMCreateForm';
import { useAuthStore } from '@/stores/authStore';
import { oidcLoginPath } from '@/api/oidc';

const statusText = {
  unlinked: '尚未关联', verified: '已核验', inactive: 'PM 项目已完成或归档',
  missing: 'PM 项目不存在或核验身份无权访问', not_configured: 'PM 核验身份尚未配置', unavailable: 'PM 暂时不可核验',
};

export function ProjectPMLinkTab({ projectCode }: { projectCode: string }) {
  const oidc = useAuthStore((s) => s.authMode === 'oidc');
  const delegated = useAuthStore((s) => s.pmDelegated);
  const cache = useQueryClient();
  const queryKey = ['project-pm-link', projectCode];
  const query = useQuery({ queryKey, queryFn: () => pmLinksApi.get(projectCode), retry: false });
  const bind = useMutation({
    mutationFn: (payload: { pm_project_id: string; change_reason: string }) => pmLinksApi.bind(projectCode, payload),
    onSuccess: (data) => { cache.setQueryData(queryKey, data); },
  });
  if (query.isLoading) return <Spin />;
  if (!query.data) return <Alert type="error" message="无法读取项目关联，请确认权限后重试" action={<Button onClick={() => { void query.refetch(); }}>重试</Button>} />;
  const { link, remote_status: remoteStatus, reference, pm_url: pmUrl } = query.data;
  return <Space direction="vertical" style={{ width: '100%' }} size="large">
    <Alert type="info" message="MDM 管登记与治理，PM 管计划与执行。已有项目关联或明确创建后都严格一对一；本页不复制状态、团队或预算，权限分别由两端后端执行。" />
    {oidc && (!delegated || remoteStatus === 'not_configured' || remoteStatus === 'unavailable') && <Alert type="info" message="当前会话需要核验 PM 用户授权" description="已保存的关联快照不会因此解除。授权后将按该用户在 PM 的实际权限核验，不会提升权限。" action={<Button href={oidcLoginPath(`/projects/${encodeURIComponent(projectCode)}`, true)}>核验 PM 用户授权</Button>} />}
    {link ? <>
      <Alert type={remoteStatus === 'verified' ? 'success' : 'warning'} message={statusText[remoteStatus]} description="建立时快照保留；核验失败不代表关联已解除。本阶段不提供改绑或删除。" />
      <Descriptions bordered column={1} items={[
        { key: 'id', label: 'PM 项目 ID', children: link.pm_project_id },
        { key: 'code', label: '编号（当前核验 / 建立快照）', children: reference?.code ?? link.pm_project_code },
        { key: 'name', label: '名称（当前核验 / 建立快照）', children: reference?.name ?? link.pm_project_name },
        { key: 'verified', label: '建立时核验时间', children: link.verified_at },
        { key: 'status', label: 'PM 当前状态', children: reference?.status ?? '未核验' },
      ]} />
      <Space><Button onClick={() => { void query.refetch(); }} loading={query.isFetching}>重新核验</Button>
        {pmUrl && <Button type="primary" href={pmUrl} target="_blank" rel="noopener noreferrer">打开 PM 执行项目</Button>}</Space>
    </> : <PermissionGuard permission="project:update"><Tabs items={[{ key: 'existing', label: '关联已有 PM 项目', children: <>
      <Typography.Paragraph>从 PM 项目地址复制准确的项目 ID；不按名称匹配。提交后将由后端核验目标，再建立关联。</Typography.Paragraph>
      <Form layout="vertical" onFinish={(values: { pm_project_id: string; change_reason: string }) => bind.mutate(values)}>
        <Form.Item name="pm_project_id" label="已有 PM 项目 ID" rules={[{ required: true }, { pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/, message: '请输入有效的 PM 项目 ID' }]}><Input autoComplete="off" /></Form.Item>
        <Form.Item name="change_reason" label="人工确认关联的原因" rules={[{ required: true }, { min: 5, max: 1000 }]}><Input.TextArea /></Form.Item>
        {bind.isError && <Alert type="error" message="关联未完成。请查看接口提示并核对项目、权限及核验配置。" style={{ marginBottom: 16 }} />}
        <Button htmlType="submit" type="primary" loading={bind.isPending}>核验并建立一对一关联</Button>
      </Form></> }, { key: 'create', label: '创建并关联 PM 项目', children: <ProjectPMCreateForm projectCode={projectCode} /> }]} />
    </PermissionGuard>}
  </Space>;
}
