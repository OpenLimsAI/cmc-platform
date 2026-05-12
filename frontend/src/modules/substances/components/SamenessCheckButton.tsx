import { useState } from 'react';
import { Alert, Button, Empty, Modal, Space, Table, Tag, Typography } from 'antd';
import { ExclamationCircleOutlined, SafetyOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { substancesApi } from '@/api/substances';
import type {
  CheckSamenessResponse,
  SamenessMatch,
  SubstanceType,
} from '@/api/types';

const { Text } = Typography;

interface Props {
  substanceType: SubstanceType;
  internalCode?: string;
  heavyChainSequence?: string;
  lightChainSequence?: string;
}

const confidenceColor = (c: number): string => {
  if (c >= 0.95) return 'red';
  if (c >= 0.8) return 'orange';
  if (c >= 0.5) return 'gold';
  return 'default';
};

const confidenceLabel = (c: number): string => {
  if (c >= 0.95) return '完全一致';
  if (c >= 0.8) return '高度疑似';
  if (c >= 0.5) return '需人工核查';
  return '弱关联';
};

export function SamenessCheckButton({
  substanceType,
  internalCode,
  heavyChainSequence,
  lightChainSequence,
}: Props) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<CheckSamenessResponse | null>(null);

  const hasAnyInput = !!(
    (internalCode && internalCode.trim()) ||
    (heavyChainSequence && heavyChainSequence.trim()) ||
    (lightChainSequence && lightChainSequence.trim())
  );

  const mutation = useMutation({
    mutationFn: () =>
      substancesApi.checkSameness({
        substance_type: substanceType,
        internal_code: internalCode?.trim() || undefined,
        heavy_chain_sequence: heavyChainSequence?.trim() || undefined,
        light_chain_sequence: lightChainSequence?.trim() || undefined,
        tolerance: 'exact',
      }),
    onSuccess: (data) => {
      setResult(data);
      setOpen(true);
    },
  });

  const matches: SamenessMatch[] = result?.matches ?? [];
  const hasHighRisk = matches.some((m) => m.confidence >= 0.85);

  return (
    <>
      <Space>
        <Button
          icon={<SafetyOutlined />}
          onClick={() => mutation.mutate()}
          loading={mutation.isPending}
          disabled={!hasAnyInput}
        >
          运行同一性判定（exact）
        </Button>
        {!hasAnyInput && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            需先填 internal_code 或至少一条序列
          </Text>
        )}
      </Space>

      <Modal
        open={open}
        title={
          <span>
            <SafetyOutlined /> 同一性判定结果
          </span>
        }
        width={780}
        onCancel={() => setOpen(false)}
        footer={<Button onClick={() => setOpen(false)}>关闭</Button>}
      >
        {hasHighRisk && (
          <Alert
            type="warning"
            showIcon
            icon={<ExclamationCircleOutlined />}
            message="检测到高度疑似的已有物质"
            description="提交前请先核实是否为同一物质，避免重复登记。如确属同一物质，应停止本次创建，转而在现有 substance 上补充信息。"
            style={{ marginBottom: 16 }}
          />
        )}

        {matches.length === 0 ? (
          <Empty description="未发现匹配，可放心创建" />
        ) : (
          <Table<SamenessMatch>
            size="small"
            rowKey="substance_code"
            dataSource={matches}
            pagination={false}
            columns={[
              {
                title: '物质编码',
                dataIndex: 'substance_code',
                width: 130,
                render: (v: string) => (
                  <a
                    href={`/substances/${v}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontFamily: 'monospace' }}
                  >
                    {v}
                  </a>
                ),
              },
              { title: '首选名称', dataIndex: 'preferred_name', ellipsis: true },
              {
                title: '状态',
                dataIndex: 'status',
                width: 90,
                render: (v: string) => <Tag>{v}</Tag>,
              },
              {
                title: '匹配字段',
                dataIndex: 'matched_fields',
                render: (fs: string[]) => (
                  <Space size={2} wrap>
                    {fs.map((f) => (
                      <Tag key={f}>{f}</Tag>
                    ))}
                  </Space>
                ),
              },
              {
                title: '置信度',
                dataIndex: 'confidence',
                width: 130,
                render: (c: number) => (
                  <Tag color={confidenceColor(c)}>
                    {(c * 100).toFixed(0)}% · {confidenceLabel(c)}
                  </Tag>
                ),
              },
            ]}
          />
        )}

        <div style={{ marginTop: 12, fontSize: 12, color: '#8c8c8c' }}>
          判定基于：HC/LC 序列 SHA-256 哈希 + internal_code 精确匹配。Phase 5 将支持基于
          CDR/编辑距离的 fuzzy 判定。
        </div>
      </Modal>

      {result && !open && (
        <Tag
          color={matches.length === 0 ? 'green' : hasHighRisk ? 'red' : 'orange'}
          style={{ marginLeft: 8 }}
        >
          {matches.length === 0
            ? '✓ 上次判定：无匹配'
            : `⚠ 上次判定：${matches.length} 条候选`}
        </Tag>
      )}
    </>
  );
}
