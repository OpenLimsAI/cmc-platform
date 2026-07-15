import { useState } from 'react';
import {
  Card,
  Col,
  Descriptions,
  Progress,
  Row,
  Statistic,
  Tabs,
  Typography,
  Space,
  Breadcrumb,
  Skeleton,
  Result,
  Button,
  message,
} from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftOutlined,
  AuditOutlined,
  CopyOutlined,
  EditOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
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
import { ProjectRelationshipTab } from '../components/ProjectRelationshipTab';
import type { ProjectDetail } from '@/api/types';
import {
  AVAILABLE_PROJECT_ACTIONS,
  OWNING_FUNCTION_OPTIONS,
  PROJECT_ACTION_LABELS,
  PROJECT_CATEGORY_OPTIONS,
  PROJECT_NATURE_OPTIONS,
  PROJECT_PHASE_OPTIONS,
  PROJECT_STATUS_COLOR,
  PROJECT_TYPE_OPTIONS,
  REGULATORY_CHANGE_LEVEL_OPTIONS,
} from '../constants';

const { Title, Paragraph } = Typography;

// UI7（V1.2 评审 UI7:A）：基于 planned_start/end + 今日推算进度百分比
function computeProjectProgress(proj: ProjectDetail): number {
  if (proj.status === 'completed') return 100;
  if (proj.status === 'terminated') return 100;
  if (!proj.planned_start_date || !proj.planned_end_date) return 0;
  const start = new Date(proj.planned_start_date).getTime();
  const end = new Date(proj.planned_end_date).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return 0;
  const now = Date.now();
  if (now < start) return 0;
  if (now > end) return 100;
  return Math.round(((now - start) / (end - start)) * 100);
}

export function ProjectDetailPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('basic');

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
  const categoryLabel =
    PROJECT_CATEGORY_OPTIONS.find((o) => o.value === proj.project_category)?.label ?? proj.project_category;
  const natureLabel =
    PROJECT_NATURE_OPTIONS.find((o) => o.value === proj.project_nature)?.label ?? proj.project_nature;
  const owningLabel =
    OWNING_FUNCTION_OPTIONS.find((o) => o.value === proj.owning_function)?.label ?? proj.owning_function;

  // UI7（V1.1 §7.2.1 行 859-887 / V1.2 评审 UI7:A 决议）：概览 Tab 1
  // = 进度条 + 团队/关联预览统计 + 详细字段表（甘特图保持 Phase 5 推迟）
  const progressPct = computeProjectProgress(proj);

  const tabs = [
    {
      key: 'basic',
      label: '概览',
      children: (
        <>
          <Card style={{ marginBottom: 16 }} title="项目概览">
            <Row gutter={[24, 16]}>
              <Col xs={24} md={12}>
                <div style={{ marginBottom: 8 }}>
                  <Typography.Text type="secondary">推进进度</Typography.Text>
                </div>
                <Progress
                  percent={progressPct}
                  status={
                    proj.status === 'terminated' ? 'exception'
                      : proj.status === 'completed' ? 'success'
                      : 'active'
                  }
                  format={(p) =>
                    proj.status === 'terminated' ? '已终止'
                      : proj.status === 'completed' ? '已完成'
                      : `${p}%`
                  }
                />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {proj.planned_start_date ?? '?'} → {proj.planned_end_date ?? '?'}
                </Typography.Text>
              </Col>
              <Col xs={24} md={12}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic title="阶段" value={phaseLabel} valueStyle={{ fontSize: 16 }} />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="优先级"
                      value={proj.priority ?? '—'}
                      valueStyle={{ fontSize: 16 }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="版本"
                      value={`v${proj.version}`}
                      valueStyle={{ fontSize: 16 }}
                    />
                  </Col>
                </Row>
                <Space style={{ marginTop: 16 }}>
                  <Button size="small" onClick={() => setActiveTab('team')}>
                    团队 →
                  </Button>
                  <Button size="small" onClick={() => setActiveTab('substances')}>
                    关联物质 →
                  </Button>
                  <Button size="small" onClick={() => setActiveTab('assets')}>
                    关联资产 →
                  </Button>
                  <Button size="small" onClick={() => setActiveTab('milestones')}>
                    里程碑 →
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>
          <Card title="详细信息">
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
              { key: 'project_category', label: '是否关联资产', children: categoryLabel },
              { key: 'project_nature', label: '项目性质', children: natureLabel },
              { key: 'owning_function', label: '主责部门（受控）', children: owningLabel },
              {
                key: 'asset_id',
                label: '关联资产',
                children: proj.asset_id ? `#${proj.asset_id}` : '—',
              },
              {
                key: 'approval_date',
                label: '立项批准日期',
                children: proj.approval_date ?? '—',
              },
              {
                key: 'approval_reference',
                label: '批准会议编号',
                children: proj.approval_reference ?? '—',
              },
              {
                key: 'governance_approval_ref',
                label: 'DGC 批准号',
                children: proj.governance_approval_ref ?? '—',
              },
              {
                key: 'regulatory_change_level',
                label: '变更级别',
                children: proj.regulatory_change_level
                  ? REGULATORY_CHANGE_LEVEL_OPTIONS.find(
                      (o) => o.value === proj.regulatory_change_level,
                    )?.label ?? proj.regulatory_change_level
                  : '—',
              },
              {
                key: 'pre_approval_required',
                label: '需预先获批',
                children:
                  proj.pre_approval_required == null
                    ? '—'
                    : proj.pre_approval_required
                      ? '是'
                      : '否',
              },
              {
                key: 'comparability_study_ref',
                label: '可比性研究编号',
                children: proj.comparability_study_ref ?? '—',
              },
              {
                key: 'legacy_project_id',
                label: '历史遗留编号',
                children: proj.legacy_project_id ?? '—',
              },
              { key: 'program_name', label: '所属 Program', children: proj.program_name ?? '—' },
              { key: 'department', label: '主责部门（自由文本）', children: proj.department ?? '—' },
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
        </>
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
      key: 'relationships',
      label: '项目关系',
      children: <ProjectRelationshipTab projectCode={proj.project_code} />,
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
              changeStatusFn={(action, comment, signature) =>
                projectsApi.changeStatus(
                  proj.project_code,
                  action as ProjectAction,
                  { comment, signature }
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
            {/* UI11（V1.1 §3.4.2）：详情页头部动作组 */}
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                void navigator.clipboard.writeText(proj.project_code);
                message.success(`已复制编码: ${proj.project_code}`);
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

      <Tabs items={tabs} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
