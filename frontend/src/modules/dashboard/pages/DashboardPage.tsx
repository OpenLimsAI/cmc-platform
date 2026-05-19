import { Card, Col, Row, Typography, Statistic, Space, theme } from 'antd';
import {
  ExperimentOutlined,
  FolderOpenOutlined,
  GoldOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
  const { token } = theme.useToken();

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => dashboardApi.summary(),
  });

  const { data: gantt = [] } = useQuery({
    queryKey: ['dashboard', 'gantt'],
    queryFn: () => dashboardApi.gantt(),
  });

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
      value: totals?.substance ?? 0,
      icon: <ExperimentOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/substances'),
    },
    {
      title: '项目',
      value: totals?.project ?? 0,
      icon: <FolderOpenOutlined style={{ fontSize: 28, color: '#52C41A' }} />,
      onClick: () => navigate('/projects'),
    },
    {
      title: '资产',
      value: totals?.asset ?? 0,
      icon: <GoldOutlined style={{ fontSize: 28, color: '#FAAD14' }} />,
      onClick: () => navigate('/assets'),
    },
    {
      title: '物料',
      value: totals?.material ?? 0,
      icon: <InboxOutlined style={{ fontSize: 28, color: '#722ED1' }} />,
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
        {cards.map((c) => (
          <Col xs={24} sm={12} lg={6} key={c.title}>
            <Card hoverable onClick={c.onClick} style={{ marginBottom: 16 }}>
              <Space size="large" style={{ width: '100%', justifyContent: 'space-between' }}>
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
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="物质类型分布"
                  data={summary.distributions.substance_by_type}
                  labelMap={optionsToLabelMap(SUBSTANCE_TYPE_OPTIONS)}
                />
              </div>
            </Col>
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="项目状态分布"
                  data={summary.distributions.project_by_status}
                  labelMap={optionsToLabelMap(PROJECT_STATUS_OPTIONS)}
                  colorMap={PROJECT_STATUS_COLOR}
                />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="项目优先级"
                  data={summary.distributions.project_by_priority}
                  labelMap={optionsToLabelMap(PROJECT_PRIORITY_OPTIONS)}
                />
              </div>
            </Col>
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="资产状态分布"
                  data={summary.distributions.asset_by_status}
                  labelMap={optionsToLabelMap(ASSET_STATUS_OPTIONS)}
                  colorMap={ASSET_STATUS_COLOR}
                />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="资产研发阶段"
                  variant="bar"
                  data={summary.distributions.asset_by_phase}
                  labelMap={optionsToLabelMap(ASSET_PHASE_OPTIONS)}
                  colorMap={optionsToColorMap(ASSET_PHASE_OPTIONS)}
                />
              </div>
            </Col>
            <Col xs={24} lg={12}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="物料类型分布"
                  data={summary.distributions.material_by_type}
                  labelMap={optionsToLabelMap(MATERIAL_TYPE_OPTIONS)}
                  colorMap={optionsToColorMap(MATERIAL_TYPE_OPTIONS)}
                />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24}>
              <div style={{ marginBottom: 16 }}>
                <DistributionPieCard
                  title="物料等级分布"
                  variant="bar"
                  data={summary.distributions.material_by_grade}
                />
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24}>
              <div style={{ marginBottom: 16 }}>
                <ProjectGanttCard projects={gantt} />
              </div>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
