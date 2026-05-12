import {
  Card,
  Descriptions,
  Tabs,
  Typography,
  Space,
  Breadcrumb,
  Skeleton,
  Result,
  Button,
} from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import { projectsApi } from '@/api/projects';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { TimeDisplay } from '@/shared/components/TimeDisplay';
import { PermissionGuard } from '@/shared/components/PermissionGuard';
import { AuditLogPanel } from '@/shared/components/AuditLogPanel';
import { StatusActionsBar } from '@/shared/components/StatusActionsBar';
import { StatusHistoryPanel } from '@/shared/components/StatusHistoryPanel';
import type { ProjectAction, ProjectStatus } from '@/api/types';
import { MilestoneTable } from '../components/MilestoneTable';
import { TeamTable } from '../components/TeamTable';
import { ProjectAssetTab } from '../components/ProjectAssetTab';
import { ProjectSubstanceTab } from '../components/ProjectSubstanceTab';
import {
  AVAILABLE_PROJECT_ACTIONS,
  PROJECT_ACTION_LABELS,
  PROJECT_PHASE_OPTIONS,
  PROJECT_STATUS_COLOR,
  PROJECT_TYPE_OPTIONS,
} from '../constants';

const { Title, Paragraph } = Typography;

export function ProjectDetailPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const {
    data: proj,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['project', code],
    queryFn: () => projectsApi.get(code!),
    enabled: !!code,
  });

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }

  if (isError || !proj) {
    return (
      <Result
        status="404"
        title="项目不存在"
        subTitle={`未找到 ${code}`}
        extra={
          <Button type="primary" onClick={() => navigate('/projects')}>
            返回项目列表
          </Button>
        }
      />
    );
  }

  const typeLabel = PROJECT_TYPE_OPTIONS.find((o) => o.value === proj.project_type)?.label ?? proj.project_type;
  const phaseLabel = proj.project_phase
    ? PROJECT_PHASE_OPTIONS.find((o) => o.value === proj.project_phase)?.label ?? proj.project_phase
    : '—';

  const tabs = [
    {
      key: 'basic',
      label: '基本信息',
      children: (
        <Card>
          <Descriptions
            bordered
            column={2}
            size="middle"
            labelStyle={{ width: 140 }}
            items={[
              { key: 'project_code', label: '项目编码', children: <code>{proj.project_code}</code> },
              { key: 'status', label: '状态', children: <StatusBadge type="project" status={proj.status} /> },
              { key: 'project_name', label: '项目名称', children: proj.project_name },
              { key: 'project_name_en', label: '英文名', children: proj.project_name_en ?? '—' },
              { key: 'project_type', label: '项目类型', children: typeLabel },
              { key: 'phase', label: '阶段', children: phaseLabel },
              { key: 'program_name', label: '所属 Program', children: proj.program_name ?? '—' },
              { key: 'department', label: '主责部门', children: proj.department ?? '—' },
              { key: 'priority', label: '优先级', children: proj.priority ?? '—' },
              {
                key: 'planned_start_date',
                label: '计划开始',
                children: proj.planned_start_date ?? '—',
              },
              {
                key: 'planned_end_date',
                label: '计划结束',
                children: proj.planned_end_date ?? '—',
              },
              {
                key: 'actual_start_date',
                label: '实际开始',
                children: proj.actual_start_date ?? '—',
              },
              {
                key: 'actual_end_date',
                label: '实际结束',
                children: proj.actual_end_date ?? '—',
              },
              {
                key: 'project_manager_id',
                label: 'PM',
                children: proj.project_manager_id ?? '—',
              },
              {
                key: 'sponsor_id',
                label: 'Sponsor',
                children: proj.sponsor_id ?? '—',
              },
              {
                key: 'objective',
                label: '目标',
                children: proj.objective ?? '—',
                span: 2,
              },
              {
                key: 'description',
                label: '描述',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {proj.description ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              {
                key: 'notes',
                label: '备注',
                children: (
                  <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                    {proj.notes ?? '—'}
                  </Paragraph>
                ),
                span: 2,
              },
              {
                key: 'version',
                label: '版本',
                children: <code>v{proj.version}</code>,
              },
              {
                key: 'updated_at',
                label: '最近更新',
                children: <TimeDisplay value={proj.updated_at} />,
              },
            ]}
          />
        </Card>
      ),
    },
    {
      key: 'milestones',
      label: '里程碑',
      children: <MilestoneTable projectCode={proj.project_code} />,
    },
    {
      key: 'team',
      label: '团队',
      children: <TeamTable projectCode={proj.project_code} />,
    },
    {
      key: 'substances',
      label: '关联物质',
      children: <ProjectSubstanceTab projectCode={proj.project_code} />,
    },
    {
      key: 'assets',
      label: '关联资产',
      children: <ProjectAssetTab projectCode={proj.project_code} />,
    },
    {
      key: 'history',
      label: '状态历史',
      children: (
        <StatusHistoryPanel
          queryKey={['project-status-history', proj.project_code]}
          loadFn={() => projectsApi.statusHistory(proj.project_code)}
          entityType="project"
          statusColor={PROJECT_STATUS_COLOR}
          emptyHint="尚无状态变更历史（项目仍在初始 draft 状态）"
        />
      ),
    },
    {
      key: 'audit',
      label: '审计',
      children: (
        <AuditLogPanel
          queryKey={['project-audit-logs', proj.project_code]}
          loadFn={(page, page_size, include_children) =>
            projectsApi.auditLogs(proj.project_code, { page, page_size, include_children })
          }
          tableLabels={{
            project: '项目主表',
            project_milestone: '里程碑',
            project_team: '团队',
            project_substance: '物质绑定',
            project_asset: '资产关联',
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
          { title: <a onClick={() => navigate('/projects')}>项目</a> },
          { title: `${proj.project_code} - ${proj.project_name}` },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space direction="vertical" size={4}>
            <Space>
              <Title level={3} style={{ margin: 0 }}>
                {proj.project_name}
              </Title>
              <StatusBadge type="project" status={proj.status} />
            </Space>
            <Typography.Text type="secondary">
              <code>{proj.project_code}</code>
              {proj.project_name_en ? ` · ${proj.project_name_en}` : ''}
            </Typography.Text>
          </Space>
          <Space wrap>
            <StatusActionsBar
              actions={(AVAILABLE_PROJECT_ACTIONS[proj.status as ProjectStatus] ?? []).map(
                (a: ProjectAction) => ({
                  action: a,
                  label: PROJECT_ACTION_LABELS[a].label,
                  danger: PROJECT_ACTION_LABELS[a].danger,
                  requiresSignature: PROJECT_ACTION_LABELS[a].requiresSignature,
                })
              )}
              changeStatusFn={(action, change_reason, password, signature_reason) =>
                projectsApi.changeStatus(
                  proj.project_code,
                  action as ProjectAction,
                  { change_reason, password, signature_reason }
                )
              }
              permission="project:approve"
              detailQueryKey={['project', proj.project_code]}
              listQueryKey={['projects']}
              entityCode={proj.project_code}
              entityTypeLabel="项目"
            />
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>
              返回列表
            </Button>
            <PermissionGuard permission="project:update">
              <Button
                type="primary"
                icon={<EditOutlined />}
                onClick={() => navigate(`/projects/${encodeURIComponent(proj.project_code)}/edit`)}
              >
                编辑
              </Button>
            </PermissionGuard>
          </Space>
        </div>
      </Card>

      <Tabs items={tabs} defaultActiveKey="basic" />
    </div>
  );
}
