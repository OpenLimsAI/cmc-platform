import { useState } from 'react';
import {
  Card,
  Descriptions,
  Tabs,
  Tag,
  Typography,
  Space,
  Breadcrumb,
  Skeleton,
  Result,
  Button,
  message,
} from 'antd';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftOutlined,
  AuditOutlined,
  CopyOutlined,
  EditOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { substancesApi } from '@/api/substances';
import { targetsApi } from '@/api/targets';
import { useAuthStore } from '@/stores/authStore';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { SubstanceTypeTag } from '@/shared/components/SubstanceTypeTag';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { AuditLogPanel } from '@/shared/components/AuditLogPanel';
import { MoleculeTargetPanel } from '@/modules/targets/components/MoleculeTargetPanel';
import { StatusActionsBar } from '@/shared/components/StatusActionsBar';
import { StatusHistoryPanel } from '@/shared/components/StatusHistoryPanel';
import { ACTION_LABELS, AVAILABLE_ACTIONS } from '../constants';
import { XrefEditor } from '../components/XrefEditor';
import { RelatedAssetsTab } from '../components/RelatedAssetsTab';
import { RelatedProjectsTab } from '../components/RelatedProjectsTab';
import { LineageTab } from '../components/LineageTab';
import type { SubstanceAction, SubstanceStatus } from '@/api/types';

const SUBSTANCE_STATUS_COLOR: Record<string, string> = {
  draft: 'gray',
  registered: 'blue',
  active: 'green',
  restricted: 'orange',
  deprecated: 'red',
  obsoleted: 'gray',
};

const { Title, Text, Paragraph } = Typography;

export function SubstanceDetailPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('basic');

  const {
    data: sub,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['substance', code],
    queryFn: () => substancesApi.get(code!, 'protein,xrefs'),
    enabled: !!code,
  });
  // 靶点域：该分子已关联的靶点（基本信息 Tab 摘要 + 页头）；无 target:read 权限则不查
  const canReadTarget = useAuthStore((st) => st.hasPermission('target:read'));
  const { data: linkedTargets = [] } = useQuery({
    queryKey: ['substance-targets', code],
    queryFn: () => targetsApi.targetsOfMolecule(code!),
    enabled: !!code && canReadTarget,
  });

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }

  if (isError || !sub) {
    return (
      <Result
        status="404"
        title="未找到该物质"
        subTitle={`物质编码：${code}`}
        extra={
          <Button type="primary" onClick={() => navigate('/substances')}>
            返回列表
          </Button>
        }
      />
    );
  }

  const tabItems = [
    {
      key: 'basic',
      label: '基本信息',
      children: (
        <Card>
          <Descriptions column={2} bordered size="small" labelStyle={{ width: 140 }}>
            <Descriptions.Item label="物质编码">{sub.substance_code}</Descriptions.Item>
            <Descriptions.Item label="内部代号">{sub.internal_code || '—'}</Descriptions.Item>
            <Descriptions.Item label="首选名称（中文）">{sub.preferred_name}</Descriptions.Item>
            <Descriptions.Item label="首选名称（英文）">
              {sub.preferred_name_en || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="类型">
              <SubstanceTypeTag type={sub.substance_type} />
            </Descriptions.Item>
            <Descriptions.Item label="模态">{sub.modality || '—'}</Descriptions.Item>
            <Descriptions.Item label="靶点" span={2}>
              {linkedTargets.length ? (
                <Space wrap size={[4, 4]}>
                  {linkedTargets.map((l) => (
                    <Tag key={`${l.target_code}-${l.relation_role}`} color={l.relation_role === 'payload_target' ? 'orange' : 'blue'}>
                      <Link to={`/targets/${encodeURIComponent(l.target_code)}`}>
                        {l.target_name}
                      </Link>
                      {l.relation_role === 'payload_target' ? '（载荷）' : ''}
                    </Tag>
                  ))}
                  <Button type="link" size="small" onClick={() => setActiveTab('targets')}>
                    维护 →
                  </Button>
                </Space>
              ) : (
                <Space>
                  <Text type="secondary">未关联</Text>
                  <Button type="link" size="small" onClick={() => setActiveTab('targets')}>
                    去「靶点」Tab 关联 →
                  </Button>
                  {sub.target ? <Text type="secondary">（旧字段：{sub.target}）</Text> : null}
                </Space>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <StatusBadge type="substance" status={sub.status} />
            </Descriptions.Item>
            <Descriptions.Item label="保密等级">{sub.confidentiality}</Descriptions.Item>
            <Descriptions.Item label="是否专有">{sub.is_proprietary ? '是' : '否'}</Descriptions.Item>
            <Descriptions.Item label="版本">{sub.version}</Descriptions.Item>
            <Descriptions.Item label="对外 UUID" span={2}>
              <Text code copyable>
                {sub.external_uuid || '—'}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>
              {sub.description || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="备注" span={2}>
              {sub.notes || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              <TimeDisplay value={sub.created_at} format="datetime" />
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              <TimeDisplay value={sub.updated_at} format="datetime" />
            </Descriptions.Item>
          </Descriptions>
        </Card>
      ),
    },
    {
      key: 'structure',
      label: '结构与序列',
      disabled: !sub.protein,
      children: sub.protein && (
        <Card>
          <Descriptions column={2} bordered size="small" labelStyle={{ width: 160 }}>
            <Descriptions.Item label="同型 (Isotype)">{sub.protein.isotype || '—'}</Descriptions.Item>
            <Descriptions.Item label="架构">{sub.protein.architecture || '—'}</Descriptions.Item>
            <Descriptions.Item label="表达系统">{sub.protein.expression_system || '—'}</Descriptions.Item>
            <Descriptions.Item label="细胞株">{sub.protein.cell_line || '—'}</Descriptions.Item>
            <Descriptions.Item label="表达载体">{sub.protein.expression_vector || '—'}</Descriptions.Item>
            <Descriptions.Item label="分子量 (Da)">
              {sub.protein.molecular_weight_da?.toLocaleString() || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="理论 pI">
              {sub.protein.pi_theoretical ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="消光系数 (M⁻¹cm⁻¹)">
              {sub.protein.extinction_coefficient?.toLocaleString() ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="重链长度">
              {sub.protein.sequence_length_hc ? `${sub.protein.sequence_length_hc} aa` : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="轻链长度">
              {sub.protein.sequence_length_lc ? `${sub.protein.sequence_length_lc} aa` : '—'}
            </Descriptions.Item>
          </Descriptions>

          {sub.protein.heavy_chain_sequence && (
            <Card type="inner" title="重链序列" style={{ marginTop: 16 }}>
              <Paragraph
                copyable
                style={{
                  fontFamily: 'Consolas, monospace',
                  fontSize: 13,
                  background: '#fafafa',
                  padding: 12,
                  borderRadius: 4,
                  wordBreak: 'break-all',
                }}
              >
                {sub.protein.heavy_chain_sequence}
              </Paragraph>
            </Card>
          )}

          {sub.protein.light_chain_sequence && (
            <Card type="inner" title="轻链序列" style={{ marginTop: 16 }}>
              <Paragraph
                copyable
                style={{
                  fontFamily: 'Consolas, monospace',
                  fontSize: 13,
                  background: '#fafafa',
                  padding: 12,
                  borderRadius: 4,
                  wordBreak: 'break-all',
                }}
              >
                {sub.protein.light_chain_sequence}
              </Paragraph>
            </Card>
          )}
        </Card>
      ),
    },
    {
      key: 'xrefs',
      label: `标识符 (${sub.xrefs?.length || 0})`,
      children: (
        <Card>
          <XrefEditor substanceCode={sub.substance_code} xrefs={sub.xrefs ?? []} />
        </Card>
      ),
    },
    {
      // 靶点域（tgt / ref.molecule_target）：分子↔靶点关联面板，与靶点详情页共用组件
      key: 'targets',
      label: '靶点',
      children: <MoleculeTargetPanel mode="substance" code={sub.substance_code} />,
    },
    {
      key: 'relations',
      label: '关联项目',
      children: <RelatedProjectsTab substanceCode={sub.substance_code} />,
    },
    {
      key: 'related_assets',
      label: '关联资产',
      children: <RelatedAssetsTab substanceCode={sub.substance_code} />,
    },
    {
      // UI9（V1.2 评审 UI9:B 决议 2026-05-13）：父/子 substance 血缘
      key: 'lineage',
      label: '血缘关系',
      children: <LineageTab substanceCode={sub.substance_code} />,
    },
    {
      key: 'history',
      label: '状态历史',
      children: (
        <StatusHistoryPanel
          queryKey={['substance-status-history', sub.substance_code]}
          loadFn={() => substancesApi.statusHistory(sub.substance_code)}
          entityType="substance"
          statusColor={SUBSTANCE_STATUS_COLOR}
          emptyHint="尚无状态变更历史（物质仍在初始 draft 状态）"
        />
      ),
    },
    {
      key: 'audit',
      label: '审计',
      children: (
        <AuditLogPanel
          queryKey={['substance-audit-logs', sub.substance_code]}
          loadFn={(page, page_size, include_children) =>
            substancesApi.auditLogs(sub.substance_code, { page, page_size, include_children })
          }
          tableLabels={{
            substance: '物质主表',
            substance_protein: '蛋白扩展',
            substance_xref: '标识符',
          }}
        />
      ),
    },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/substances')}>物质</a> },
          { title: `${sub.substance_code} - ${sub.preferred_name}` },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/substances')}>
            返回
          </Button>
          {/* UI11（V1.1 §3.4.2）：详情页右上角动作组 */}
          <Space size="small">
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(sub.substance_code);
                message.success(`已复制编码: ${sub.substance_code}`);
              }}
            >
              复制编码
            </Button>
            <Button
              size="small"
              icon={<ShareAltOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(window.location.href);
                message.success('已复制详情页链接');
              }}
            >
              分享
            </Button>
            <Button
              size="small"
              icon={<AuditOutlined />}
              onClick={() => setActiveTab('audit')}
            >
              查看审计
            </Button>
          </Space>
        </Space>
        <Space align="start" size={16} style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {sub.preferred_name}
              <span style={{ marginLeft: 16 }}>
                <StatusBadge type="substance" status={sub.status} />
              </span>
              {sub.confidentiality === 'restricted' && (
                <span style={{ marginLeft: 8, fontSize: 14 }}>🔒 受限</span>
              )}
            </Title>
            <Space size="middle" style={{ marginTop: 8 }}>
              <Text strong>{sub.substance_code}</Text>
              {sub.internal_code && <Text type="secondary">· {sub.internal_code}</Text>}
              {sub.modality && <Text type="secondary">· {sub.modality}</Text>}
              {linkedTargets.length > 0 && (
                <Text type="secondary">· 靶点: {[...new Set(linkedTargets.map((l) => l.target_name))].join(' / ')}</Text>
              )}
            </Space>
          </div>
          <Space>
            <StatusActionsBar
              actions={(AVAILABLE_ACTIONS[sub.status as SubstanceStatus] ?? []).map(
                (a: SubstanceAction) => ({
                  action: a,
                  label: ACTION_LABELS[a].label,
                  danger: ACTION_LABELS[a].danger,
                  requiresSignature: ACTION_LABELS[a].requiresSignature,
                })
              )}
              changeStatusFn={(action, comment, signature) =>
                substancesApi.changeStatus(
                  sub.substance_code,
                  action as SubstanceAction,
                  { comment, signature }
                )
              }
              permission="substance:approve"
              detailQueryKey={['substance', sub.substance_code]}
              listQueryKey={['substances']}
              entityCode={sub.substance_code}
              entityTypeLabel="物质"
            />
            <PermissionGuard permission="substance:update">
              <Button
                icon={<EditOutlined />}
                onClick={() => navigate(`/substances/${sub.substance_code}/edit`)}
              >
                编辑
              </Button>
            </PermissionGuard>
          </Space>
        </Space>
      </Card>

      <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
