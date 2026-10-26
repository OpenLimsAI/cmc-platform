import { Card, Empty, Result, Skeleton, Space, Tag, Timeline, Tooltip, Typography } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { StatusHistoryItem } from '@/api/types';
import { StatusBadge } from './StatusBadge';

const { Text } = Typography;

interface Props {
  queryKey: readonly unknown[];
  loadFn: () => Promise<StatusHistoryItem[]>;
  /** StatusBadge 的 type，控制旧/新状态标签的色板 */
  entityType: 'substance' | 'project' | 'asset' | 'material';
  /** 新状态 → Timeline 点颜色 */
  statusColor?: Record<string, string>;
  emptyHint?: string;
}

/**
 * 通用状态变更历史时间线。SRS/PRS/未来 ARS/MM 共用。
 */
export function StatusHistoryPanel({
  queryKey,
  loadFn,
  entityType,
  statusColor = {},
  emptyHint = '尚无状态变更历史（仍在初始状态）',
}: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey,
    queryFn: loadFn,
  });

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 5 }} />
      </Card>
    );
  }
  if (isError) return <Result status="error" title="加载失败" />;
  if (!data || data.length === 0) {
    return (
      <Card>
        <Empty description={emptyHint} />
      </Card>
    );
  }

  return (
    <Card>
      <Timeline
        mode="left"
        items={data.map((h) => ({
          label: (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {dayjs(h.changed_at).format('YYYY-MM-DD HH:mm:ss')}
            </Text>
          ),
          color: statusColor[h.new_status] || 'blue',
          children: (
            <div>
              <Space size="small">
                {h.old_status ? (
                  <StatusBadge type={entityType} status={h.old_status} />
                ) : (
                  <Text type="secondary">—</Text>
                )}
                <Text type="secondary">→</Text>
                <StatusBadge type={entityType} status={h.new_status} />
                {h.e_signature_id && (
                  <Tooltip
                    title={`电子签名 #${h.e_signature_id}（21 CFR Part 11 §11.50）：等同手写签名，绑定本次状态变更。`}
                  >
                    <Tag icon={<SafetyCertificateOutlined />} color="purple">
                      已签名 #{h.e_signature_id}
                    </Tag>
                  </Tooltip>
                )}
              </Space>
              <div style={{ marginTop: 4, color: '#595959' }}>{h.change_reason}</div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                操作人 ID: {h.changed_by}
              </Text>
            </div>
          ),
        }))}
      />
    </Card>
  );
}
