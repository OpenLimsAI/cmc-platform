import { api, unwrap, unwrapList } from './client';
import type {
  AuditLogItem,
  ProjectAction,
  ProjectBrief,
  ProjectCreatePayload,
  ProjectDetail,
  ProjectListQuery,
  ProjectMilestone,
  ProjectMilestoneCreatePayload,
  ProjectMilestoneUpdatePayload,
  ProjectStatusChangePayload,
  ProjectAssetLink,
  ProjectAssetLinkFromProjectPayload,
  ProjectSubstanceLink,
  ProjectSubstanceLinkCreatePayload,
  ProjectTeamMember,
  ProjectTeamMemberCreatePayload,
  ProjectUpdatePayload,
  StateChangeResponse,
  StatusHistoryItem,
} from './types';

export const projectsApi = {
  list: (query: ProjectListQuery = {}) =>
    unwrapList<ProjectBrief>(api.get('/projects', { params: query })),

  get: (code: string) =>
    unwrap<ProjectDetail>(api.get(`/projects/${encodeURIComponent(code)}`)),

  create: (payload: ProjectCreatePayload) =>
    unwrap<ProjectDetail>(api.post('/projects', payload)),

  update: (code: string, payload: ProjectUpdatePayload) =>
    unwrap<ProjectDetail>(api.put(`/projects/${encodeURIComponent(code)}`, payload)),

  // axios DELETE 走 `data` 传 body
  delete: (code: string, change_reason: string) =>
    api.delete(`/projects/${encodeURIComponent(code)}`, {
      data: { change_reason },
    }),

  auditLogs: (
    code: string,
    query: { page?: number; page_size?: number; include_children?: boolean } = {}
  ) =>
    unwrapList<AuditLogItem>(
      api.get(`/projects/${encodeURIComponent(code)}/audit-logs`, { params: query })
    ),

  // 状态机端点（冒号语法，encodeURIComponent 把 : 编为 %3A，浏览器/FastAPI 都能解析）
  changeStatus: (code: string, action: ProjectAction, payload: ProjectStatusChangePayload) =>
    unwrap<StateChangeResponse>(
      api.post(`/projects/${encodeURIComponent(code)}:${action}`, payload)
    ),

  statusHistory: (code: string) =>
    unwrap<StatusHistoryItem[]>(
      api.get(`/projects/${encodeURIComponent(code)}/status-history`)
    ),

  // 里程碑
  listMilestones: (code: string) =>
    unwrap<ProjectMilestone[]>(
      api.get(`/projects/${encodeURIComponent(code)}/milestones`)
    ),

  addMilestone: (code: string, payload: ProjectMilestoneCreatePayload) =>
    unwrap<ProjectMilestone>(
      api.post(`/projects/${encodeURIComponent(code)}/milestones`, payload)
    ),

  updateMilestone: (code: string, mid: number, payload: ProjectMilestoneUpdatePayload) =>
    unwrap<ProjectMilestone>(
      api.put(`/projects/${encodeURIComponent(code)}/milestones/${mid}`, payload)
    ),

  deleteMilestone: (code: string, mid: number, change_reason: string) =>
    api.delete(`/projects/${encodeURIComponent(code)}/milestones/${mid}`, {
      data: { change_reason },
    }),

  // 团队
  listTeam: (code: string, include_left = false) =>
    unwrap<ProjectTeamMember[]>(
      api.get(`/projects/${encodeURIComponent(code)}/team`, {
        params: { include_left },
      })
    ),

  addTeamMember: (code: string, payload: ProjectTeamMemberCreatePayload) =>
    unwrap<ProjectTeamMember>(
      api.post(`/projects/${encodeURIComponent(code)}/team`, payload)
    ),

  removeTeamMember: (code: string, team_id: number, change_reason?: string) =>
    api.delete(`/projects/${encodeURIComponent(code)}/team/${team_id}`, {
      data: { change_reason },
    }),

  // ref.project_substance link/unlink (DM-MDM-001 §11.2 复合 PK)
  listSubstances: (code: string, include_deleted = false) =>
    unwrap<ProjectSubstanceLink[]>(
      api.get(`/projects/${encodeURIComponent(code)}/substances`, {
        params: { include_deleted },
      })
    ),

  linkSubstance: (code: string, payload: ProjectSubstanceLinkCreatePayload) =>
    unwrap<ProjectSubstanceLink>(
      api.post(`/projects/${encodeURIComponent(code)}/substances`, payload)
    ),

  unlinkSubstance: (
    code: string,
    substance_code: string,
    relation_type: string,
    change_reason?: string,
  ) =>
    api.delete(
      `/projects/${encodeURIComponent(code)}/substances/${encodeURIComponent(substance_code)}/${encodeURIComponent(relation_type)}`,
      { data: { change_reason } },
    ),

  // ref.project_asset（§11.4）
  listAssets: (code: string, include_deleted = false) =>
    unwrap<ProjectAssetLink[]>(
      api.get(`/projects/${encodeURIComponent(code)}/assets`, {
        params: { include_deleted },
      })
    ),

  linkAsset: (code: string, payload: ProjectAssetLinkFromProjectPayload) =>
    unwrap<ProjectAssetLink>(
      api.post(`/projects/${encodeURIComponent(code)}/assets`, payload)
    ),

  unlinkAsset: (code: string, asset_code: string, change_reason?: string) =>
    api.delete(
      `/projects/${encodeURIComponent(code)}/assets/${encodeURIComponent(asset_code)}`,
      { data: { change_reason } },
    ),
};
