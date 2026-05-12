import { api, unwrap, unwrapList } from './client';
import type {
  AssetSubstanceLink,
  AuditLogItem,
  CheckSamenessRequest,
  CheckSamenessResponse,
  ProjectSubstanceLink,
  StatusHistoryItem,
  SubstanceAction,
  SubstanceBrief,
  SubstanceCreatePayload,
  SubstanceDetail,
  SubstanceListQuery,
  SubstanceStatusChangePayload,
  SubstanceUpdatePayload,
  SubstanceXref,
  SubstanceXrefCreateInput,
  SubstanceXrefUpdateInput,
} from './types';

export const substancesApi = {
  list: (query: SubstanceListQuery = {}) =>
    unwrapList<SubstanceBrief>(api.get('/substances', { params: query })),

  get: (code: string, expand?: string) =>
    unwrap<SubstanceDetail>(
      api.get(`/substances/${encodeURIComponent(code)}`, { params: { expand } })
    ),

  create: (payload: SubstanceCreatePayload) =>
    unwrap<SubstanceDetail>(api.post('/substances', payload)),

  update: (code: string, payload: SubstanceUpdatePayload) =>
    unwrap<SubstanceDetail>(api.put(`/substances/${encodeURIComponent(code)}`, payload)),

  // 后端要求 change_reason（21 CFR Part 11）；axios DELETE 走 `data` 传 body
  delete: (code: string, change_reason: string) =>
    api.delete(`/substances/${encodeURIComponent(code)}`, {
      data: { change_reason },
    }),

  // 状态机端点（路径含冒号，encodeURIComponent 会把 : 编成 %3A，浏览器/FastAPI 都能解析）
  changeStatus: (code: string, action: SubstanceAction, payload: SubstanceStatusChangePayload) =>
    unwrap<SubstanceDetail>(
      api.post(`/substances/${encodeURIComponent(code)}:${action}`, payload)
    ),

  // xrefs 子资源
  addXref: (code: string, payload: SubstanceXrefCreateInput) =>
    unwrap<SubstanceXref>(
      api.post(`/substances/${encodeURIComponent(code)}/xrefs`, payload)
    ),

  updateXref: (code: string, xrefId: number, payload: SubstanceXrefUpdateInput) =>
    unwrap<SubstanceXref>(
      api.put(`/substances/${encodeURIComponent(code)}/xrefs/${xrefId}`, payload)
    ),

  deleteXref: (code: string, xrefId: number) =>
    api.delete(`/substances/${encodeURIComponent(code)}/xrefs/${xrefId}`),

  // 审计与状态历史
  auditLogs: (
    code: string,
    query: { page?: number; page_size?: number; include_children?: boolean } = {}
  ) =>
    unwrapList<AuditLogItem>(
      api.get(`/substances/${encodeURIComponent(code)}/audit-logs`, { params: query })
    ),

  statusHistory: (code: string) =>
    unwrap<StatusHistoryItem[]>(
      api.get(`/substances/${encodeURIComponent(code)}/status-history`)
    ),

  checkSameness: (payload: CheckSamenessRequest) =>
    unwrap<CheckSamenessResponse>(api.post('/substances:check-sameness', payload)),

  // 反向查询：该物质关联到哪些项目
  listProjects: (code: string, include_deleted = false) =>
    unwrap<ProjectSubstanceLink[]>(
      api.get(`/substances/${encodeURIComponent(code)}/projects`, {
        params: { include_deleted },
      })
    ),

  // 反向查询：该物质作为组分参与的资产
  listAssets: (code: string, include_deleted = false) =>
    unwrap<AssetSubstanceLink[]>(
      api.get(`/substances/${encodeURIComponent(code)}/assets`, {
        params: { include_deleted },
      })
    ),
};
