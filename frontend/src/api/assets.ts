import { api, unwrap, unwrapList } from './client';
import type {
  AssetAction,
  AssetBrief,
  AssetCreatePayload,
  AssetDetail,
  AssetListQuery,
  AssetMarketId,
  AssetMarketIdCreatePayload,
  AssetMarketIdUpdatePayload,
  AssetStatusChangePayload,
  AssetSubstanceLink,
  AssetSubstanceLinkCreatePayload,
  AssetUpdatePayload,
  AuditLogItem,
  ProjectAssetLink,
  ProjectAssetLinkFromAssetPayload,
  StateChangeResponse,
  StatusHistoryItem,
} from './types';

export const assetsApi = {
  list: (query: AssetListQuery = {}) =>
    unwrapList<AssetBrief>(api.get('/assets', { params: query })),

  get: (code: string) =>
    unwrap<AssetDetail>(api.get(`/assets/${encodeURIComponent(code)}`)),

  create: (payload: AssetCreatePayload) =>
    unwrap<AssetDetail>(api.post('/assets', payload)),

  update: (code: string, payload: AssetUpdatePayload) =>
    unwrap<AssetDetail>(api.put(`/assets/${encodeURIComponent(code)}`, payload)),

  delete: (code: string, change_reason: string) =>
    api.delete(`/assets/${encodeURIComponent(code)}`, {
      data: { change_reason },
    }),

  auditLogs: (
    code: string,
    query: { page?: number; page_size?: number; include_children?: boolean } = {}
  ) =>
    unwrapList<AuditLogItem>(
      api.get(`/assets/${encodeURIComponent(code)}/audit-logs`, { params: query })
    ),

  // 状态机
  changeStatus: (code: string, action: AssetAction, payload: AssetStatusChangePayload) =>
    unwrap<StateChangeResponse>(
      api.post(`/assets/${encodeURIComponent(code)}:${action}`, payload)
    ),

  statusHistory: (code: string) =>
    unwrap<StatusHistoryItem[]>(
      api.get(`/assets/${encodeURIComponent(code)}/status-history`)
    ),

  // 多市场注册号
  listMarketIds: (code: string) =>
    unwrap<AssetMarketId[]>(
      api.get(`/assets/${encodeURIComponent(code)}/market-ids`)
    ),

  addMarketId: (code: string, payload: AssetMarketIdCreatePayload) =>
    unwrap<AssetMarketId>(
      api.post(`/assets/${encodeURIComponent(code)}/market-ids`, payload)
    ),

  updateMarketId: (
    code: string,
    market_id_pk: number,
    payload: AssetMarketIdUpdatePayload,
  ) =>
    unwrap<AssetMarketId>(
      api.put(
        `/assets/${encodeURIComponent(code)}/market-ids/${market_id_pk}`,
        payload,
      )
    ),

  deleteMarketId: (code: string, market_id_pk: number, change_reason: string) =>
    api.delete(
      `/assets/${encodeURIComponent(code)}/market-ids/${market_id_pk}`,
      { data: { change_reason } },
    ),

  // ref.asset_substance（§11.3）
  listSubstances: (code: string, include_deleted = false) =>
    unwrap<AssetSubstanceLink[]>(
      api.get(`/assets/${encodeURIComponent(code)}/substances`, {
        params: { include_deleted },
      })
    ),

  linkSubstance: (code: string, payload: AssetSubstanceLinkCreatePayload) =>
    unwrap<AssetSubstanceLink>(
      api.post(`/assets/${encodeURIComponent(code)}/substances`, payload)
    ),

  unlinkSubstance: (
    code: string,
    substance_code: string,
    component_role: string,
    change_reason?: string,
  ) =>
    api.delete(
      `/assets/${encodeURIComponent(code)}/substances/${encodeURIComponent(substance_code)}/${encodeURIComponent(component_role)}`,
      { data: { change_reason } },
    ),

  // ref.project_asset 反向（§11.4，资产侧）
  listProjects: (code: string, include_deleted = false) =>
    unwrap<ProjectAssetLink[]>(
      api.get(`/assets/${encodeURIComponent(code)}/projects`, {
        params: { include_deleted },
      })
    ),

  linkProject: (code: string, payload: ProjectAssetLinkFromAssetPayload) =>
    unwrap<ProjectAssetLink>(
      api.post(`/assets/${encodeURIComponent(code)}/projects`, payload)
    ),

  unlinkProject: (code: string, project_code: string, change_reason?: string) =>
    api.delete(
      `/assets/${encodeURIComponent(code)}/projects/${encodeURIComponent(project_code)}`,
      { data: { change_reason } },
    ),
};
