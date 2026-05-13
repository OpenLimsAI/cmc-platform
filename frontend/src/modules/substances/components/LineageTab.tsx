import { Card, Empty, Space, Table, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { EntityCodeLink } from '@/shared/components/EntityCodeLink';

const { Text, Paragraph } = Typography;

interface LineageBrief {
  substance_code: string;
  preferred_name: string;
  substance_type: string;
  status: string;
  as_role?: 'antibody' | 'linker' | 'payload';
}

interface LineageResponse {
  self_type: string;
  parents: {
    antibody: LineageBrief | null;
    linker: LineageBrief | null;
    payload: LineageBrief | null;
  };
  children: LineageBrief[];
}

const ROLE_COLOR: Record<string, string> = {
  antibody: 'blue',
  linker: 'orange',
  payload: 'purple',
};
const ROLE_LABEL: Record<string, string> = {
  antibody: '抗体 (antibody)',
  linker: '连接子 (linker)',
  payload: '载荷 (payload)',
};

/** UI9（V1.1 §6.2.5 / V1.2 评审 UI9:B 决议）：物质血缘关系 Tab
 *  显示 ADC 的父结构（antibody/linker/payload）+ 反向 — 哪些 ADC 引用了当前 substance
 */
export function LineageTab({ substanceCode }: { substanceCode: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['substance-lineage', substanceCode],
    queryFn: async () => {
      const resp = await api.get<{ data: LineageResponse }>(
        `/substances/${encodeURIComponent(substanceCode)}/lineage`
      );
      return resp.data.data;
    },
  });

  if (isLoading) return <Card loading />;
  if (!data) return null;

  const hasParents =
    data.parents.antibody || data.parents.linker || data.parents.payload;
  const hasChildren = data.children.length > 0;

  if (!hasParents && !hasChildren) {
    return (
      <Card>
        <Empty
          description={
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              该物质无 ADC 血缘关系（既不是 ADC，也没有被任何 ADC 引用）
            </Paragraph>
          }
        />
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {data.self_type === 'adc' && (
        <Card title="父结构（当前物质是 ADC，由以下组分构成）" size="small">
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            {(['antibody', 'linker', 'payload'] as const).map((role) => {
              const p = data.parents[role];
              return (
                <Space key={role} size="middle">
                  <Tag color={ROLE_COLOR[role]} style={{ minWidth: 110 }}>
                    {ROLE_LABEL[role]}
                  </Tag>
                  {p ? (
                    <>
                      <EntityCodeLink type="substance" code={p.substance_code} />
                      <Text>{p.preferred_name}</Text>
                      <Tag>{p.substance_type}</Tag>
                      <Tag color={p.status === 'active' ? 'green' : 'default'}>
                        {p.status}
                      </Tag>
                    </>
                  ) : (
                    <Text type="secondary">— 未指定</Text>
                  )}
                </Space>
              );
            })}
          </Space>
        </Card>
      )}

      {hasChildren && (
        <Card
          title={`被哪些 ADC 引用（${data.children.length}）`}
          size="small"
        >
          <Table<LineageBrief>
            size="small"
            rowKey="substance_code"
            dataSource={data.children}
            pagination={false}
            columns={[
              {
                title: 'ADC 编码',
                dataIndex: 'substance_code',
                render: (c: string) => <EntityCodeLink type="substance" code={c} />,
              },
              { title: '名称', dataIndex: 'preferred_name', ellipsis: true },
              {
                title: '当前物质在该 ADC 中的角色',
                dataIndex: 'as_role',
                width: 220,
                render: (r: string) => (
                  <Tag color={ROLE_COLOR[r] ?? 'default'}>{ROLE_LABEL[r] ?? r}</Tag>
                ),
              },
              {
                title: '状态',
                dataIndex: 'status',
                width: 100,
                render: (s: string) => (
                  <Tag color={s === 'active' ? 'green' : 'default'}>{s}</Tag>
                ),
              },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}
