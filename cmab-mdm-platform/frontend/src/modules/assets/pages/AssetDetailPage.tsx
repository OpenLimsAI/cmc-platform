import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Result,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  AuditOutlined,
  CopyOutlined,
  EditOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { assetsApi } from '@/api/assets';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { AuditLogPanel } from '@/shared/components/AuditLogPanel';
import { StatusActionsBar } from '@/shared/components/StatusActionsBar';
import { StatusHistoryPanel } from '@/shared/components/StatusHistoryPanel';
import type { AssetAction, AssetStatus } from '@/api/types';
import { AssetProjectTab } from '../components/AssetProjectTab';
import { AssetSubstanceTab } from '../components/AssetSubstanceTab';
import { MarketIdTable } from '../components/MarketIdTable';
import {
  ASSET_ACTION_LABELS,
  ASSET_PHASE_OPTIONS,
  ASSET_STATUS_COLOR,
  ASSET_TYPE_OPTIONS,
  AVAILABLE_ASSET_ACTIONS,
} from '../constants';

const { Title, Paragraph } = Typography;

export function AssetDetailPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('basic');

  const {
    data: asset,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['asset', code],
    queryFn: () => assetsApi.get(code!),
    enabled: !!code,
  });

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }

  if (isError || !asset) {
    return (
      <Result
        status="404"
        title="资产不存在"
        subTitle={`未找到 ${code}`}
        extra={
          <Button type="primary" onClick={() => navigate('/assets')}>
            返回资产列表
          </Button>
        }
      />
    );
  }

  const typeLabel = ASSET_TYPE_OPTIONS.find((o) => o.value === asset.asset_type)?.label ?? asset.asset_type;
  const phaseDef = ASSET_PHASE_OPTIONS.find((o) => o.value === asset.current_phase);

  // UI8（V1.1 §7.3 行 925 / V1.2 评审 UI8:A）：当前阶段时间线
  // 9 个 phase（discovery → marketed）顺序展示；discontinued 单独显示
  const PHASE_ORDER: string[] = [
    'discovery', 'preclinical', 'phase_1', 'phase_2', 'phase_3',
    'submission', 'approved', 'marketed',
  ];
  const currentIdx = PHASE_ORDER.indexOf(asset.current_phase);
  const isDiscontinued = asset.current_phase === 'discontinued';
  const phaseTimeline = PHASE_ORDER.map((p, i) => {
    const def = ASSET_PHASE_OPTIONS.find((o) => o.value === p);
    let color: string;
    let dotLabel: string;
    if (isDiscontinued) {
      color = 'gray';
      dotLabel = '—';
    } else if (i < currentIdx) {
      color = 'green';
      dotLabel = '✓';
    } else if (i === currentIdx) {
      color = 'blue';
      dotLabel = '●';
    } else {
      color = 'gray';
      dotLabel = '○';
    }
    return {
      color,
      label: i === currentIdx && asset.phase_change_at ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {new Date(asset.phase_change_at).toLocaleDateString('zh-CN')}
        </Typography.Text>
      ) : undefined,
      children: (
        <span>
          <Tag color={def?.color ?? 'default'} style={{ marginRight: 8 }}>{dotLabel}</Tag>
          <Typography.Text strong={i === currentIdx}>
            {def?.label ?? p}
          </Typography.Text>
          {i === currentIdx && (
            <Typography.Text type="success" style={{ marginLeft: 8, fontSize: 12 }}>
              · 当前
            </Typography.Text>
          )}
        </span>
      ),
    };
  });

  const tabs = [
    {
      key: 'basic',
      label: '基本信息',
      children: (
        <>
          <Card style={{ marginBottom: 16 }} title="当前阶段时间线">
            {isDiscontinued ? (
              <Typography.Text type="danger">
                ✗ 已停止上市（discontinued）
              </Typography.Text>
            ) : (
              <Timeline mode="left" items={phaseTimeline} />
            )}
          </Card>
          <Card title="详细信息">
          <Descriptions
            bordered
            column={2}
            size="middle"
            labelStyle={{ width: 140 }}
            items={[
              { key: 'asset_code', label: '资产编码', children: <code>{asset.asset_code}</code> },
              { key: 'status', label: '状态', children: <StatusBadge type="asset" status={asset.status} /> },
              { key: 'internal_name', label: '内部名称', children: asset.internal_name },
              { key: 'trade_name', label: '商品名', children: asset.trade_name ?? '—' },
              { key: 'inn_name', label: 'INN 通用名', children: asset.inn_name ?? '—' },
              { key: 'asset_type', label: '资产类型', children: typeLabel },
              {
                key: 'current_phase',
                label: '当前阶段',
                children: <Tag color={phaseDef?.color ?? 'default'}>{phaseDef?.label ?? asset.current_phase}</Tag>,
              },
              {
                key: 'phase_change_at',
                label: '阶段变更时间',
                children: asset.phase_change_at ? <TimeDisplay value={asset.phase_change_at} /> : '—',
              },
              { key: 'therapeutic_area', label: '治疗领域', children: asset.therapeutic_area ?? '—' },
              {
                key: 'is_commercial',
                label: '商业化',
                children: asset.is_commercial ? '✓ 已商业化' : '—',
              },
              { key: 'dosage_form', label: '剂型', children: asset.dosage_form ?? '—' },
              { key: 'strength', label: '规格', children: asset.strength ?? '—' },
              { key: 'route', label: '给药途径', children: asset.route_of_administration ?? '—' },
              {
                key: 'first_approval_date',
                label: '首批准日期',
                children: asset.first_approval_date ?? '—',
              },
              {
                key: 'first_launch_date',
                label: '首上市日期',
                children: asset.first_launch_date ?? '—',
              },
              {
                key: 'indication',
                label: '适应症',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {asset.indication ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              {
                key: 'description',
                label: '描述',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {asset.description ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              { key: 'version', label: '版本', children: <code>v{asset.version}</code> },
              {
                key: 'updated_at',
                label: '最近更新',
                children: <TimeDisplay value={asset.updated_at} />,
              },
            ]}
          />
          </Card>
        </>
      ),
    },
    {
      key: 'market_ids',
      label: '多市场注册号',
      children: <MarketIdTable assetCode={asset.asset_code} />,
    },
    {
      key: 'substances',
      label: '关联物质',
      children: (
        <AssetSubstanceTab assetCode={asset.asset_code} assetStatus={asset.status} />
      ),
    },
    {
      key: 'projects',
      label: '关联项目',
      children: (
        <AssetProjectTab assetCode={asset.asset_code} assetStatus={asset.status} />
      ),
    },
    {
      key: 'history',
      label: '状态历史',
      children: (
        <StatusHistoryPanel
          queryKey={['asset-status-history', asset.asset_code]}
          loadFn={() => assetsApi.statusHistory(asset.asset_code)}
          entityType="asset"
          statusColor={ASSET_STATUS_COLOR}
          emptyHint="尚无状态变更历史"
        />
      ),
    },
    {
      key: 'audit',
      label: '审计',
      children: (
        <AuditLogPanel
          queryKey={['asset-audit-logs', asset.asset_code]}
          loadFn={(page, page_size, include_children) =>
            assetsApi.auditLogs(asset.asset_code, { page, page_size, include_children })
          }
          tableLabels={{
            asset: '资产主表',
            asset_market_id: '多市场注册号',
            asset_substance: '物质组分',
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
          { title: <a onClick={() => navigate('/assets')}>资产</a> },
          { title: `${asset.asset_code} - ${asset.internal_name}` },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space direction="vertical" size={4}>
            <Space>
              <Title level={3} style={{ margin: 0 }}>
                {asset.internal_name}
              </Title>
              <StatusBadge type="asset" status={asset.status} />
              <Tag color={phaseDef?.color ?? 'default'}>{phaseDef?.label ?? asset.current_phase}</Tag>
            </Space>
            <Typography.Text type="secondary">
              <code>{asset.asset_code}</code>
              {asset.trade_name ? ` · 商品名 ${asset.trade_name}` : ''}
              {asset.inn_name ? ` · INN ${asset.inn_name}` : ''}
            </Typography.Text>
          </Space>
          <Space wrap>
            <StatusActionsBar
              actions={(AVAILABLE_ASSET_ACTIONS[asset.status as AssetStatus] ?? []).map(
                (a: AssetAction) => ({
                  action: a,
                  label: ASSET_ACTION_LABELS[a].label,
                  danger: ASSET_ACTION_LABELS[a].danger,
                  requiresSignature: ASSET_ACTION_LABELS[a].requiresSignature,
                })
              )}
              changeStatusFn={(action, comment, signature) =>
                assetsApi.changeStatus(
                  asset.asset_code,
                  action as AssetAction,
                  { comment, signature }
                )
              }
              permission="asset:update"
              detailQueryKey={['asset', asset.asset_code]}
              listQueryKey={['assets']}
              entityCode={asset.asset_code}
              entityTypeLabel="资产"
            />
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/assets')}>
              返回列表
            </Button>
            {/* UI11（V1.1 §3.4.2）：详情页头部动作组 */}
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(asset.asset_code);
                message.success(`已复制编码: ${asset.asset_code}`);
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
            <Button size="small" icon={<AuditOutlined />} onClick={() => setActiveTab('audit')}>
              查看审计
            </Button>
            <PermissionGuard permission="asset:update">
              <Button
                type="primary"
                icon={<EditOutlined />}
                onClick={() => navigate(`/assets/${encodeURIComponent(asset.asset_code)}/edit`)}
              >
                编辑
              </Button>
            </PermissionGuard>
          </Space>
        </div>
      </Card>

      <Tabs items={tabs} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
