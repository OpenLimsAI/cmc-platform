import { useState } from 'react';
import { Card, Space, Switch, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { substancesApi } from '@/api/substances';
import type { ProjectSubstanceLink } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { RELATION_TYPE_OPTIONS } from '@/modules/projects/constants';

const { Text } = Typography;

interface Props {
  substanceCode: string;
}

export function RelatedProjectsTab({ substanceCode }: Props) {
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['substance-related-projects', substanceCode, includeDeleted],
    queryFn: () => substancesApi.listProjects(substanceCode, includeDeleted),
  });

  const columns = [
    {
      title: '项目编码',
      dataIndex: 'project_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="project" code={code} />,
    },
    { title: '项目名称', dataIndex: 'project_name', ellipsis: true },
    {
      title: '项目状态',
      dataIndex: 'project_status',
      width: 100,
      render: (s: string) => <StatusBadge type="project" status={s} />,
    },
    {
      title: '关联类型',
      dataIndex: 'relation_type',
      width: 110,
      render: (r: string) => {
        const def = RELATION_TYPE_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? r}</Tag>;
      },
    },
    {
      title: '主要',
      dataIndex: 'is_primary',
      width: 70,
      render: (v: boolean) => (v ? <Tag color="gold">主</Tag> : '—'),
    },
    {
      title: '绑定时间',
      dataIndex: 'created_at',
      width: 150,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '取消时间',
      dataIndex: 'deleted_at',
      width: 150,
      render: (v?: string | null) =>
        v ? <Text type="danger">{dayjs(v).format('YYYY-MM-DD HH:mm')}</Text> : '—',
    },
  ];

  return (
    <Card
      title={
        <Space>
          <span>关联项目</span>
          <Switch
            size="small"
            checked={includeDeleted}
            onChange={setIncludeDeleted}
            checkedChildren="含已取消"
            unCheckedChildren="仅活动"
          />
        </Space>
      }
    >
      <Table<ProjectSubstanceLink>
        size="middle"
        rowKey={(r) => `${r.project_code}:${r.relation_type}`}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">该物质尚未关联到任何项目</Text> }}
      />
    </Card>
  );
}
