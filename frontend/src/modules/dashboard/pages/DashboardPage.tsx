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
import { assetsApi } from '@/api/assets';
import { materialsApi } from '@/api/materials';
import { projectsApi } from '@/api/projects';
import { substancesApi } from '@/api/substances';

const { Title, Text } = Typography;

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const { token } = theme.useToken();

  // 简化：用各域列表的 pagination.total 作为仪表盘统计
  const { data: substanceStats } = useQuery({
    queryKey: ['stats', 'substances'],
    queryFn: () => substancesApi.list({ page: 1, page_size: 1 }),
  });
  const { data: projectStats } = useQuery({
    queryKey: ['stats', 'projects'],
    queryFn: () => projectsApi.list({ page: 1, page_size: 1 }),
  });
  const { data: assetStats } = useQuery({
    queryKey: ['stats', 'assets'],
    queryFn: () => assetsApi.list({ page: 1, page_size: 1 }),
  });
  const { data: materialStats } = useQuery({
    queryKey: ['stats', 'materials'],
    queryFn: () => materialsApi.list({ page: 1, page_size: 1 }),
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

  const cards = [
    {
      title: '物质',
      value: substanceStats?.pagination.total ?? 0,
      icon: <ExperimentOutlined style={{ fontSize: 28, color: token.colorPrimary }} />,
      onClick: () => navigate('/substances'),
    },
    {
      title: '项目',
      value: projectStats?.pagination.total ?? 0,
      icon: <FolderOpenOutlined style={{ fontSize: 28, color: '#52C41A' }} />,
      onClick: () => navigate('/projects'),
    },
    {
      title: '资产',
      value: assetStats?.pagination.total ?? 0,
      icon: <GoldOutlined style={{ fontSize: 28, color: '#FAAD14' }} />,
      onClick: () => navigate('/assets'),
    },
    {
      title: '物料',
      value: materialStats?.pagination.total ?? 0,
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
                <Statistic title={c.title} value={c.value} />
                {c.icon}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="待办事项" style={{ marginBottom: 16 }}>
            <Text type="secondary">暂无待办（功能开发中）</Text>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="最近访问" style={{ marginBottom: 16 }}>
            <Text type="secondary">暂无最近访问记录（功能开发中）</Text>
          </Card>
        </Col>
      </Row>

      <Card title="系统公告">
        <Text>📢 CMAB MDM Portal v1.0.0 已上线，欢迎使用。如有问题请联系 IT 部门。</Text>
      </Card>
    </div>
  );
}
