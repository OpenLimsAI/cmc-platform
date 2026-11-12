import { Card, Col, Row, Typography, Statistic, Space, theme } from 'antd';
import {
  AimOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  GoldOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { MicroscopeIcon } from '@/shared/components/icons';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/api/dashboard';
import { SUBSTANCE_TYPE_OPTIONS } from '@/modules/substances/constants';
import {
  PROJECT_STATUS_OPTIONS,
  PROJECT_PRIORITY_OPTIONS,
  PROJECT_STATUS_COLOR,
} from '@/modules/projects/constants';
import {
  ASSET_PHASE_OPTIONS,
  ASSET_STATUS_OPTIONS,
  ASSET_STATUS_COLOR,
} from '@/modules/assets/constants';
import {
  MATERIAL_TYPE_OPTIONS,
} from '@/modules/materials/constants';
import {
  EQUIPMENT_CATEGORY_OPTIONS,
  EQUIPMENT_MASTER_STATUS_OPTIONS,
} from '@/modules/equipments/constants';
import { TARGET_STATUS_OPTIONS } from '@/modules/targets/constants';
import { DistributionPieCard } from '../components/DistributionPieCard';
import { TrendLineCard } from '../components/TrendLineCard';
import { ProjectGanttCard } from '../components/ProjectGanttCard';

const { Title, Text } = Typography;

function optionsToLabelMap(
  options: { value: string; label: string }[],
): Record<string, string> {
  return Object.fromEntries(options.map((o) => [o.value, o.label]));
}

function optionsToColorMap(
  options: { value: string; color: string }[],
): Record<string, string> {
  return Object.fromEntries(options.map((o) => [o.value, o.color]));
}

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const hasAnyRead = useAuthStore((s) => s.hasAnyReadPermission());
  const canReadProject = useAuthStore((s) => s.hasPermission('project:read'));
  const navigate = useNavigate();
  const { token } = theme.useToken();

  // 2026-09-10：后端按读权限裁剪，只回用户能进的域；一个都不能进的账号后端 403，这里直接回首页落点
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => dashboardApi.summary(),
    enabled: hasAnyRead,
  });

  const { data: gantt = [] } = useQuery({
    queryKey: ['dashboard', 'gantt'],
    queryFn: () => dashboardApi.gantt(),
    enabled: canReadProject,
  });

  const visible = new Set<string>(summary?.visible_domains ?? []);
  const show = (domain: string) => visible.has(domain);

  if (!hasAnyRead) return <Navigate to="/" replace />;

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 6) return '夜深了';
    if (hour < 12) return '早上好';
    if (hour < 14) return '中午好';
    if (hour < 18) return '下午好';
    return '晚上好';
  })();

  const today = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });

  const totals = summary?.totals;

  const cards = [
    {
      title: '物质',
      domain: 'substance',
      value: totals?.substance ?? 0,
      icon: <ExperimentOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/substances'),
    },
    {
      title: '资产',
      domain: 'asset',
      value: totals?.asset ?? 0,
      icon: <GoldOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/assets'),
    },
    {
      title: '项目',
      domain: 'project',
      value: totals?.project ?? 0,
      icon: <FolderOpenOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/projects'),
    },
    {
      title: '靶点',
      domain: 'target',
      value: totals?.target ?? 0,
      icon: <AimOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/targets'),
    },
    {
      title: '设备',
      domain: 'equipment',
      value: totals?.equipment ?? 0,
      icon: <MicroscopeIcon style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/equipments'),
    },
    {
      title: '物料',
      domain: 'material',
      value: totals?.material ?? 0,
      icon: <InboxOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/materials'),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ marginTop: 0, marginBottom: 4 }}>
          {greeting}，{user?.full_name || user?.username}
        </Title>
        <Text type="secondary">{today}</Text>
      </Card>

      <Row gutter={16}>
        {cards.filter((c) => show(c.domain)).map((c) => (
          <Col flex="1 1 0" style={{ minWidth: 150 }} key={c.title}>
            <Card hoverable onClick={c.onClick} style={{ marginBottom: 16 }}>
              <Space size="middle" style={{ width: '100%', justifyContent: 'space-between' }}>
                <Statistic title={c.title} value={c.value} loading={summaryLoading} />
                {c.icon}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      {summary && (
        <>
          <Row gutter={16}>
            <Col xs={24} lg={24}>
              <div style={{ marginBottom: 16 }}>
                <TrendLineCard trend={summary.trend_30d} />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            {show('substance') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="物质类型分布"
                    data={summary.distributions.substance_by_type ?? []}
                    labelMap={optionsToLabelMap(SUBSTANCE_TYPE_OPTIONS)}
                  />
                </div>
              </Col>
            )}
            {show('project') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="项目状态分布"
                    data={summary.distributions.project_by_status ?? []}
                    labelMap={optionsToLabelMap(PROJECT_STATUS_OPTIONS)}
                    colorMap={PROJECT_STATUS_COLOR}
                  />
                </div>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            {show('project') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="项目优先级"
                    data={summary.distributions.project_by_priority ?? []}
                    labelMap={optionsToLabelMap(PROJECT_PRIORITY_OPTIONS)}
                  />
                </div>
              </Col>
            )}
            {show('asset') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="资产状态分布"
                    data={summary.distributions.asset_by_status ?? []}
                    labelMap={optionsToLabelMap(ASSET_STATUS_OPTIONS)}
                    colorMap={ASSET_STATUS_COLOR}
                  />
                </div>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            {show('asset') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="资产研发阶段"
                    variant="bar"
                    data={summary.distributions.asset_by_phase ?? []}
                    labelMap={optionsToLabelMap(ASSET_PHASE_OPTIONS)}
                    colorMap={optionsToColorMap(ASSET_PHASE_OPTIONS)}
                  />
                </div>
              </Col>
            )}
            {show('material') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="物料类型分布"
                    data={summary.distributions.material_by_type ?? []}
                    labelMap={optionsToLabelMap(MATERIAL_TYPE_OPTIONS)}
                    colorMap={optionsToColorMap(MATERIAL_TYPE_OPTIONS)}
                  />
                </div>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            {show('material') && (
              <Col xs={24}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="物料等级分布"
                    variant="bar"
                    data={summary.distributions.material_by_grade ?? []}
                  />
                </div>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            {show('equipment') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="设备类别分布"
                    data={summary.distributions.equipment_by_category ?? []}
                    labelMap={optionsToLabelMap(EQUIPMENT_CATEGORY_OPTIONS)}
                  />
                </div>
              </Col>
            )}
            {show('equipment') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="设备主数据状态分布"
                    data={summary.distributions.equipment_by_status ?? []}
                    labelMap={optionsToLabelMap(EQUIPMENT_MASTER_STATUS_OPTIONS)}
                  />
                </div>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            {show('target') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="靶点状态分布"
                    data={summary.distributions.target_by_status ?? []}
                    labelMap={optionsToLabelMap(TARGET_STATUS_OPTIONS)}
                  />
                </div>
              </Col>
            )}
            {show('target') && (
              <Col xs={24} lg={12}>
                <div style={{ marginBottom: 16 }}>
                  <DistributionPieCard
                    title="靶点 UniProt 条目类型"
                    data={summary.distributions.target_by_entry_type ?? []}
                    labelMap={{
                      'UniProtKB reviewed (Swiss-Prot)': 'Swiss-Prot（人工审阅）',
                      'UniProtKB unreviewed (TrEMBL)': 'TrEMBL（自动注释）',
                    }}
                  />
                </div>
              </Col>
            )}
          </Row>

          {canReadProject && (
            <Row gutter={16}>
              <Col xs={24}>
                <div style={{ marginBottom: 16 }}>
                  <ProjectGanttCard projects={gantt} />
                </div>
              </Col>
            </Row>
          )}
        </>
      )}
    </div>
  );
}
