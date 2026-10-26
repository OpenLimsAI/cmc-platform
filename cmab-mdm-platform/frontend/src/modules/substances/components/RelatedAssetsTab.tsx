import { useState } from 'react';
import { Card, Space, Switch, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { substancesApi } from '@/api/substances';
import type { AssetSubstanceLink } from '@/api/types';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';
import { COMPONENT_ROLE_OPTIONS } from '@/modules/assets/constants';

const { Text } = Typography;

interface Props {
  substanceCode: string;
}

export function RelatedAssetsTab({ substanceCode }: Props) {
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['substance-related-assets', substanceCode, includeDeleted],
    queryFn: () => substancesApi.listAssets(substanceCode, includeDeleted),
  });

  const columns = [
    {
      title: '资产编码',
      dataIndex: 'asset_code',
      width: 140,
      render: (code: string) => <EntityCodeLink type="asset" code={code} />,
    },
    { title: '资产名称', dataIndex: 'asset_internal_name', ellipsis: true },
    {
      title: '资产状态',
      dataIndex: 'asset_status',
      width: 100,
      render: (s: string) => <StatusBadge type="asset" status={s} />,
    },
    {
      title: '组分角色',
      dataIndex: 'component_role',
      width: 110,
      render: (r: string) => {
        const def = COMPONENT_ROLE_OPTIONS.find((o) => o.value === r);
        return <Tag color={def?.color ?? 'default'}>{def?.label ?? r}</Tag>;
      },
    },
    {
      title: '活性成分',
      dataIndex: 'is_active_ingredient',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : '—'),
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
          <span>关联资产</span>
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
      <Table<AssetSubstanceLink>
        size="middle"
        rowKey={(r) => `${r.asset_code}:${r.component_role}`}
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">该物质尚未作为任何资产的组分</Text> }}
      />
    </Card>
  );
}
