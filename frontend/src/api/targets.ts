import { api, unwrap, unwrapList } from './client';
import type { AuditLogItem } from './types';

// ============== 靶点域（tgt.target / ref.molecule_target / tgt.target_source_snapshot）==============
// 设计决策：docs/decisions/2026-08-17-target-domain.md
export type TargetStatus = 'draft' | 'published' | 'retired';
export type TargetAction = 'publish' | 'retire';
export type MoleculeTargetRole = 'antibody_target' | 'payload_target' | 'other';
export type SnapshotSource = 'uniprot' | 'chembl_target' | 'chembl_molecule' | 'chembl_mechanism' | 'other';

// ---- UniProt 标准子结构（0051）----
export interface UniprotKeyword {
  id: string | null; // KW-0675
  name: string; // Receptor
  category: string | null; // Molecular function / Cellular component / Biological process / ...
}
export interface UniprotSubcellularLocation {
  id: string | null; // SL-0039
  location: string; // Cell membrane
  topology: string | null; // Single-pass type I membrane protein
  topology_id: string | null;
  orientation: string | null;
  molecule: string | null;
}
export interface UniprotDomain {
  type: string; // Domain / Region / Topological domain / Transmembrane / Signal / Chain
  description: string | null;
  start: number | null;
  end: number | null;
}

/** UniProt 标准字段：全部由「拉取」自动带出，人不手填 */
export interface TargetUniprotFields {
  entry_type?: string | null;
  protein_existence?: string | null;
  cd_antigen_names?: string[] | null;
  gene_synonyms?: string[] | null;
  tax_id?: number | null;
  keywords?: UniprotKeyword[] | null;
  subcellular_locations?: UniprotSubcellularLocation[] | null;
  ec_numbers?: string[] | null;
  domains?: UniprotDomain[] | null;
  sequence_length?: number | null;
  mol_weight?: number | null;
  sequence_md5?: string | null;
  sequence_crc64?: string | null;
  sequence?: string | null; // 完整单字母序列（UniProt canonical）
  uniprot_entry_version?: number | null;
  uniprot_fetched_at?: string | null;
}

export interface TargetBrief {
  target_code: string; // TGT-NNNNNN（系统取号）
  target_name: string;
  uniprot_id: string | null;
  gene_symbol: string | null;
  organism: string | null;
  entry_type: string | null;
  cd_antigen_names: string[] | null;
  keywords: UniprotKeyword[] | null;
  subcellular_locations: UniprotSubcellularLocation[] | null;
  status: TargetStatus;
  created_at: string;
  updated_at: string;
}

export interface TargetDetail extends Required<TargetUniprotFields> {
  target_id: number;
  target_code: string;
  target_name: string;
  uniprot_id: string | null;
  gene_symbol: string | null;
  organism: string | null;
  aliases: string[] | null;
  status: TargetStatus;
  description: string | null;
  notes: string | null;
  extra: Record<string, unknown> | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at: string | null;
  deleted_by: number | null;
}

export interface TargetCreatePayload extends TargetUniprotFields {
  target_name: string;
  uniprot_id?: string | null;
  gene_symbol?: string | null;
  organism?: string | null;
  aliases?: string[] | null;
  description?: string | null;
  notes?: string | null;
}

export interface TargetUpdatePayload extends Partial<TargetCreatePayload> {
  change_reason?: string;
}

export interface TargetListQuery {
  q?: string;
  keyword?: string;
  keyword_category?: string;
  location?: string;
  entry_type?: string;
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

export interface MoleculeTargetLinkCreatePayload {
  substance_code: string;
  relation_role: MoleculeTargetRole;
  moa?: string | null;
  action_type?: string | null;
  binding_epitope_or_domain?: string | null;
  chembl_mechanism_id?: number | null;
  needs_confirm?: boolean;
  notes?: string | null;
}

export interface MoleculeTargetLinkUpdatePayload {
  change_reason?: string;
  moa?: string | null;
  action_type?: string | null;
  binding_epitope_or_domain?: string | null;
  chembl_mechanism_id?: number | null;
  needs_confirm?: boolean;
  notes?: string | null;
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

export interface TargetPrefillHints {
  entry_type: string | null;
  entry_version: number | null;
  tax_id: number | null;
  sequence_length: number | null;
  is_human: boolean | null;
  is_reviewed: boolean | null;
  redirected_from: string | null;
}

export interface TargetSnapshotCreatePayload {
  source: SnapshotSource;
  source_id?: string | null;
  source_version?: string | null;
  source_url?: string | null;
  fetched_at: string;
  payload: Record<string, unknown>;
  license?: string | null;
}

export interface TargetPrefillResponse {
  accession: string;
  existing: TargetBrief | null; // 库里已有（含次级 accession）→ 应建关联而非新建
  form: Partial<TargetCreatePayload>;
  hints: TargetPrefillHints;
  snapshot: TargetSnapshotCreatePayload;
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

  // 按当前 uniprot_id 重新拉取并覆盖标准字段 + 追加快照
  refreshUniprot: (code: string, change_reason: string) =>
    unwrap<TargetDetail>(
      api.post(`/targets/${encodeURIComponent(code)}:refresh-uniprot`, { change_reason }, { timeout: 45000 }),
    ),

  // 分子↔靶点关联（ref.molecule_target）
  molecules: (code: string) =>
    unwrap<MoleculeTargetLink[]>(api.get(`/targets/${encodeURIComponent(code)}/molecules`)),
  targetsOfMolecule: (substanceCode: string) =>
    unwrap<MoleculeTargetLink[]>(api.get(`/targets/by-molecule/${encodeURIComponent(substanceCode)}`)),
  addMolecule: (code: string, payload: MoleculeTargetLinkCreatePayload) =>
    unwrap<MoleculeTargetLink>(api.post(`/targets/${encodeURIComponent(code)}/molecules`, payload)),
  updateMolecule: (code: string, substanceCode: string, role: MoleculeTargetRole, payload: MoleculeTargetLinkUpdatePayload) =>
    unwrap<MoleculeTargetLink>(
      api.put(`/targets/${encodeURIComponent(code)}/molecules/${encodeURIComponent(substanceCode)}/${role}`, payload),
    ),
  removeMolecule: (code: string, substanceCode: string, role: MoleculeTargetRole, change_reason: string) =>
    api.delete(`/targets/${encodeURIComponent(code)}/molecules/${encodeURIComponent(substanceCode)}/${role}`, {
      data: { change_reason },
    }),

  // 审计历史（主表 + 关联表）
  auditLogs: (code: string, query: { page?: number; page_size?: number; include_children?: boolean } = {}) =>
    unwrapList<AuditLogItem>(api.get(`/targets/${encodeURIComponent(code)}/audit-logs`, { params: query })),

  // 外部源快照
  snapshots: (code: string) =>
    unwrap<TargetSnapshotBrief[]>(api.get(`/targets/${encodeURIComponent(code)}/snapshots`)),
  addSnapshot: (code: string, payload: TargetSnapshotCreatePayload) =>
    unwrap<TargetSnapshotBrief>(api.post(`/targets/${encodeURIComponent(code)}/snapshots`, payload)),

  // 按 UniProt accession 拉一条做表单预填（只读，不落库；后端出网，约 2–5 秒）
  prefillUniprot: (accession: string) =>
    unwrap<TargetPrefillResponse>(
      api.get('/targets/prefill/uniprot', { params: { accession }, timeout: 45000 }),
    ),
};
