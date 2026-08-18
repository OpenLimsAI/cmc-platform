import { api, unwrap, unwrapList } from './client';

// ============== 靶点域（tgt.target / ref.molecule_target / tgt.target_source_snapshot）==============
// 设计决策：docs/decisions/2026-08-17-target-domain.md
export type TargetType = '受体' | '配体·细胞因子' | '表面抗原' | '酶' | '其他';
export type TargetLocation = '膜型' | '可溶型' | '两者都有' | '胞内';
export type TargetStatus = 'draft' | 'published' | 'retired';
export type TargetAction = 'publish' | 'retire';
export type MoleculeTargetRole = 'antibody_target' | 'payload_target' | 'other';
export type SnapshotSource = 'uniprot' | 'chembl_target' | 'chembl_molecule' | 'chembl_mechanism' | 'other';

export interface TargetBrief {
  target_code: string; // TGT-NNNNNN（系统取号）
  target_name: string;
  uniprot_id: string | null;
  gene_symbol: string | null;
  organism: string | null;
  target_type: TargetType;
  target_location: TargetLocation;
  status: TargetStatus;
  created_at: string;
  updated_at: string;
}

export interface TargetDetail extends TargetBrief {
  target_id: number;
  aliases: string[] | null;
  description: string | null;
  notes: string | null;
  extra: Record<string, unknown> | null;
  created_by: number;
  updated_by: number;
  deleted_at: string | null;
  deleted_by: number | null;
}

export interface TargetCreatePayload {
  target_name: string;
  uniprot_id?: string | null;
  gene_symbol?: string | null;
  organism?: string | null;
  aliases?: string[] | null;
  target_type: TargetType;
  target_location: TargetLocation;
  description?: string | null;
  notes?: string | null;
}

export interface TargetUpdatePayload extends Partial<TargetCreatePayload> {
  change_reason?: string;
}

export interface TargetListQuery {
  q?: string;
  target_type?: string;
  target_location?: string;
  status?: string;
  uniprot_id?: string;
  page?: number;
  page_size?: number;
  sort?: string;
}

export interface MoleculeTargetLink {
  molecule_id: number;
  substance_code: string;
  substance_name: string | null;
  target_id: number;
  target_code: string;
  target_name: string;
  relation_role: MoleculeTargetRole;
  moa: string | null;
  action_type: string | null;
  binding_epitope_or_domain: string | null;
  chembl_mechanism_id: number | null;
  needs_confirm: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TargetSnapshotBrief {
  snapshot_id: number;
  target_id: number;
  source: SnapshotSource;
  source_id: string | null;
  source_version: string | null;
  source_url: string | null;
  fetched_at: string;
  license: string | null;
  created_at: string;
  created_by: number;
}

export const targetsApi = {
  list: (query: TargetListQuery = {}) =>
    unwrapList<TargetBrief>(api.get('/targets', { params: query })),

  get: (code: string) =>
    unwrap<TargetDetail>(api.get(`/targets/${encodeURIComponent(code)}`)),

  create: (payload: TargetCreatePayload) =>
    unwrap<TargetDetail>(api.post('/targets', payload)),

  update: (code: string, payload: TargetUpdatePayload) =>
    unwrap<TargetDetail>(api.put(`/targets/${encodeURIComponent(code)}`, payload)),

  delete: (code: string, change_reason: string) =>
    api.delete(`/targets/${encodeURIComponent(code)}`, { data: { change_reason } }),

  // 轻档审核：publish / retire（只要 change_reason，无电签）
  changeStatus: (code: string, action: TargetAction, change_reason: string) =>
    unwrap<TargetDetail>(
      api.post(`/targets/${encodeURIComponent(code)}:${action}`, { change_reason }),
    ),

  // 分子关联（只读展示；关联维护一期走 API / 二期做面板）
  molecules: (code: string) =>
    unwrap<MoleculeTargetLink[]>(api.get(`/targets/${encodeURIComponent(code)}/molecules`)),

  // 外部源快照（只读展示）
  snapshots: (code: string) =>
    unwrap<TargetSnapshotBrief[]>(api.get(`/targets/${encodeURIComponent(code)}/snapshots`)),
};
