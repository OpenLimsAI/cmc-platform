import { Button, Result, Spin } from 'antd';
import { Navigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { pmLinksApi } from '@/api/pmLinks';

export function PMProjectContextPage() {
  const { pmProjectId = '' } = useParams();
  const query = useQuery({ queryKey: ['pm-project-context', pmProjectId], queryFn: () => pmLinksApi.resolve(pmProjectId), retry: false });
  if (query.isLoading) return <Spin />;
  if (query.data) return <Navigate replace to={`/projects/${encodeURIComponent(query.data.project_code)}`} />;
  return <Result status="warning" title="无法打开登记项目" subTitle="该 PM 项目尚未建立有效关联，或当前 MDM 账号无权读取。请由有权限的人员在登记项目中人工关联。" extra={<Button onClick={() => { void query.refetch(); }}>重新查询</Button>} />;
}
