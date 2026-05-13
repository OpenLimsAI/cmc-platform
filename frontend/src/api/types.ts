/**
 * 与后端 API-MDM-001 对齐的核心类型
 * （后续可通过 pnpm gen:api 自动从 OpenAPI 生成完整类型）
 */

// ============== 通用响应包络 ==============
export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ResponseMeta {
  request_id?: string;
  timestamp: string;
  api_version: string;
  pagination?: Pagination;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
  meta: ResponseMeta;
}

export interface ApiListResponse<T> {
  code: number;
  message: string;
  data: T[];
  meta: ResponseMeta;
}

export interface ApiErrorInfo {
  type: string;
  details: { field?: string; message: string }[];
  trace_id?: string;
}

// ============== Auth ==============
export interface RoleBrief {
  role_id: number;
  role_code: string;
  role_name: string;
}

export interface UserMe {
  user_id: number;
  username: string;
  email: string;
  full_name: string;
  full_name_en?: string | null;
  department?: string | null;
  title?: string | null;
  phone?: string | null;
  status: string;
  mfa_enabled: boolean;
  last_login_at?: string | null;
  roles: RoleBrief[];
  permissions: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponseUser {
  user_id: number;
  username: string;
  full_name: string;
  department?: string | null;
  title?: string | null;
  roles: string[];
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: LoginResponseUser;
}

// ============== Substance ==============
export type SubstanceType =
  | 'mab'
  | 'bispecific'
  | 'adc'
  | 'fusion'
  | 'small_molecule'
  | 'oligonucleotide'
  | 'other';

export type SubstanceStatus =
  | 'draft'
  | 'registered'
  | 'active'
  | 'restricted'
  | 'deprecated'
  | 'obsoleted';

export type Confidentiality = 'public' | 'internal' | 'restricted';

export interface SubstanceBrief {
  substance_code: string;
  substance_type: SubstanceType;
  internal_code?: string | null;
  preferred_name: string;
  preferred_name_en?: string | null;
  target?: string | null;
  status: SubstanceStatus;
  confidentiality: Confidentiality;
  inn?: string | null;
  cas_number?: string | null;
  project_count: number;
  asset_count: number;
  material_count: number;
  created_at: string;
  updated_at: string;
}

export interface SubstanceXref {
  xref_id?: number;
  xref_type: string;
  xref_value: string;
  xref_source?: string | null;
  region?: string | null;
  is_primary: boolean;
  effective_date?: string | null;
  expiry_date?: string | null;
  notes?: string | null;
}

export interface ProteinExtension {
  heavy_chain_sequence?: string | null;
  light_chain_sequence?: string | null;
  additional_chains?: Record<string, unknown> | null;
  sequence_length_hc?: number | null;
  sequence_length_lc?: number | null;
  sequence_hash_hc?: string | null;
  sequence_hash_lc?: string | null;
  isotype?: string | null;
  architecture?: string | null;
  disulfide_bonds?: Record<string, unknown> | null;
  glycosylation_sites?: Record<string, unknown> | null;
  ptm_info?: Record<string, unknown> | null;
  expression_system?: string | null;
  cell_line?: string | null;
  expression_vector?: string | null;
  molecular_weight_da?: number | null;
  pi_theoretical?: number | null;
  extinction_coefficient?: number | null;
}

export interface SubstanceDetail {
  substance_id: number;
  substance_code: string;
  substance_type: SubstanceType;
  internal_code?: string | null;
  preferred_name: string;
  preferred_name_en?: string | null;
  target?: string | null;
  target_type?: string | null;
  modality?: string | null;
  is_proprietary: boolean;
  confidentiality: Confidentiality;
  external_uuid?: string | null;
  description?: string | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
  status: SubstanceStatus;
  version: number;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  registered_at?: string | null;
  registered_by?: number | null;
  protein?: ProteinExtension | null;
  xrefs: SubstanceXref[];
}

export interface SubstanceListQuery {
  q?: string;
  substance_type?: string;
  status?: string;
  target?: string;
  confidentiality?: string;
  page?: number;
  page_size?: number;
  sort?: string;
}

export type XrefType =
  | 'INN'
  | 'USAN'
  | 'CAS'
  | 'UNII'
  | 'GSRS_UUID'
  | 'ChEMBL'
  | 'DRUGBANK'
  | 'TRADE_NAME'
  | 'GENERIC_NAME'
  | 'HISTORICAL_CODE'
  | 'PROJECT_CODE'
  | 'OTHER';

export interface SubstanceXrefInput {
  xref_type: XrefType;
  xref_value: string;
  xref_source?: string;
  region?: string;
  is_primary?: boolean;
  effective_date?: string;
  expiry_date?: string;
  notes?: string;
}

export interface ProteinExtensionInput {
  heavy_chain_sequence?: string;
  light_chain_sequence?: string;
  additional_chains?: Record<string, unknown>;
  sequence_length_hc?: number;
  sequence_length_lc?: number;
  isotype?: string;
  architecture?: string;
  disulfide_bonds?: Record<string, unknown>;
  expression_system?: string;
  cell_line?: string;
  expression_vector?: string;
  molecular_weight_da?: number;
  pi_theoretical?: number;
  extinction_coefficient?: number;
}

export interface SubstanceCreatePayload {
  substance_type: SubstanceType;
  internal_code?: string;
  preferred_name: string;
  preferred_name_en?: string;
  target?: string;
  target_type?: string;
  modality?: string;
  is_proprietary?: boolean;
  confidentiality?: Confidentiality;
  description?: string;
  notes?: string;
  protein?: ProteinExtensionInput;
  xrefs?: SubstanceXrefInput[];
}

export interface SubstanceUpdatePayload {
  version: number;
  change_reason?: string;
  internal_code?: string;
  preferred_name?: string;
  preferred_name_en?: string;
  target?: string;
  target_type?: string;
  modality?: string;
  is_proprietary?: boolean;
  confidentiality?: Confidentiality;
  description?: string;
  notes?: string;
  protein?: ProteinExtensionInput;
}

export type SubstanceAction = 'approve' | 'activate' | 'restrict' | 'deprecate' | 'obsolete';

// API-MDM-001 V1.1 §6.5 / §7.4 / §8.x 状态机端点公用契约
export type SignatureMeaning = 'approve' | 'review' | 'release' | 'witness' | 'reject';

export interface SignatureBlock {
  /** 当前用户密码（21 CFR Part 11 §11.200）*/
  password: string;
  /** 签名含义（可选，后端按 action 推断默认值）*/
  meaning?: SignatureMeaning;
  /** 签名理由（21 CFR Part 11 §11.50，独立于 comment）*/
  reason: string;
}

export interface StateChangeResponse {
  // 三域共用响应；其中一个 entity_code 字段非空
  substance_code?: string;
  project_code?: string;
  asset_code?: string;
  old_status: string;
  new_status: string;
  signature_id?: number | null;
  registered_at?: string | null;
  registered_by?: number | null;
  version: number;
}

export interface SubstanceStatusChangePayload {
  // 业务变更原因（写 audit_log.reason + status_history.change_reason）
  comment: string;
  // GxP 关键动作必传（approve / activate / deprecate / obsolete）
  signature?: SignatureBlock;
}

export interface SubstanceXrefCreateInput extends SubstanceXrefInput {}

export interface SubstanceXrefUpdateInput {
  xref_type?: XrefType;
  xref_value?: string;
  xref_source?: string;
  region?: string;
  is_primary?: boolean;
  effective_date?: string;
  expiry_date?: string;
  notes?: string;
}

// ============== Project (DM-MDM-001 §9.2) ==============
export type ProjectType =
  | 'cmc'
  | 'preclinical'
  | 'clinical'
  | 'regulatory'
  | 'commercial'
  | 'platform'
  | 'other';

// §9.2 project_phase: VARCHAR(32) 无 CHECK 约束，但保留前端常用建议值
export type ProjectPhase =
  | 'discovery'
  | 'preclinical'
  | 'phase_1'
  | 'phase_2'
  | 'phase_3'
  | 'submission'
  | 'approved'
  | 'marketed'
  | 'discontinued'
  | 'na';

export type ProjectStatus =
  | 'proposed'
  | 'initiated'
  | 'active'
  | 'on_hold'
  | 'completed'
  | 'terminated';

export type ProjectPriority = 'high' | 'medium' | 'low';

export interface ProjectBrief {
  project_code: string;
  project_name: string;
  project_name_en?: string | null;
  project_type: ProjectType;
  project_phase?: string | null;
  department?: string | null;
  priority?: string | null;
  status: ProjectStatus;
  project_manager_id?: number | null;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  project_id: number;
  project_code: string;
  project_name: string;
  project_name_en?: string | null;
  project_type: ProjectType;
  project_phase?: string | null;
  parent_project_id?: number | null;
  program_name?: string | null;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  project_manager_id?: number | null;
  sponsor_id?: number | null;
  department?: string | null;
  budget_total?: string | null;
  budget_currency?: string | null;
  budget_actual?: string | null;
  objective?: string | null;
  scope?: string | null;
  deliverables?: string | null;
  success_criteria?: string | null;
  priority?: ProjectPriority | null;
  confidentiality: 'public' | 'internal' | 'restricted';
  description?: string | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
  status: ProjectStatus;
  version: number;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
}

export interface ProjectListQuery {
  q?: string;
  project_type?: string;
  project_phase?: string;
  status?: string;
  department?: string;
  project_manager_id?: number;
  page?: number;
  page_size?: number;
  sort?: string;
}

export interface ProjectCreatePayload {
  project_name: string;
  project_name_en?: string;
  project_type: ProjectType;
  project_phase?: string;
  parent_project_id?: number;
  program_name?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  actual_start_date?: string;
  actual_end_date?: string;
  project_manager_id?: number;
  sponsor_id?: number;
  department?: string;
  budget_total?: number;
  budget_currency?: string;
  budget_actual?: number;
  objective?: string;
  scope?: string;
  deliverables?: string;
  success_criteria?: string;
  priority?: ProjectPriority;
  confidentiality?: 'public' | 'internal' | 'restricted';
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export interface ProjectUpdatePayload {
  version: number;
  change_reason?: string;
  project_name?: string;
  project_name_en?: string;
  project_type?: ProjectType;
  project_phase?: string;
  parent_project_id?: number;
  program_name?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  actual_start_date?: string;
  actual_end_date?: string;
  project_manager_id?: number;
  sponsor_id?: number;
  department?: string;
  budget_total?: number;
  budget_currency?: string;
  budget_actual?: number;
  objective?: string;
  scope?: string;
  deliverables?: string;
  success_criteria?: string;
  priority?: ProjectPriority;
  confidentiality?: 'public' | 'internal' | 'restricted';
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export type ProjectAction =
  | 'approve'
  | 'start'
  | 'hold'
  | 'resume'
  | 'complete'
  | 'terminate';

export interface ProjectStatusChangePayload {
  comment: string;
  // GxP 关键动作（approve / complete / terminate）必传 signature 嵌套对象
  signature?: SignatureBlock;
}

// ============== Project milestones (DM-MDM-001 §9.3) ==============
export type MilestoneType = 'gate' | 'deliverable' | 'decision';

export type MilestoneStatus =
  | 'planned'
  | 'in_progress'
  | 'completed'
  | 'delayed'
  | 'cancelled';

export interface ProjectMilestone {
  milestone_id: number;
  project_id: number;
  milestone_name: string;
  milestone_type?: MilestoneType | null;
  planned_date: string;  // §9.3 NOT NULL
  actual_date?: string | null;
  status: MilestoneStatus;
  description?: string | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
}

export interface ProjectMilestoneCreatePayload {
  milestone_name: string;
  milestone_type?: MilestoneType;
  planned_date: string;  // NOT NULL
  actual_date?: string;
  status?: MilestoneStatus;
  description?: string;
}

export interface ProjectMilestoneUpdatePayload {
  change_reason?: string;
  milestone_name?: string;
  milestone_type?: MilestoneType;
  planned_date?: string;
  actual_date?: string;
  status?: MilestoneStatus;
  description?: string;
}

// ============== Project team (DM-MDM-001 §9.4) ==============
// role 任意字符串（无 CHECK 约束）；前端常用值见 constants
export interface ProjectTeamMember {
  team_id: number;
  project_id: number;
  user_id: number;
  role: string;
  function_area?: string | null;
  allocation_pct?: number | null;
  joined_at: string;  // DATE
  left_at?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ProjectTeamMemberCreatePayload {
  user_id: number;
  role: string;
  function_area?: string;
  allocation_pct?: number;
  notes?: string;
}

// ============== ref.project_substance (跨域绑定 - DM-MDM-001 §11.2) ==============
export type RelationType =
  | 'primary'
  | 'secondary'
  | 'reference'
  | 'control'
  | 'derivative';

export interface ProjectSubstanceLink {
  relation_type: RelationType;
  is_primary: boolean;
  notes?: string | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at?: string | null;
  deleted_by?: number | null;
  project_code: string;
  project_name: string;
  project_status: string;
  project_type: string;
  substance_code: string;
  substance_preferred_name: string;
  substance_status: string;
  substance_type: string;
}

export interface ProjectSubstanceLinkCreatePayload {
  substance_code: string;
  relation_type: RelationType;
  is_primary?: boolean;
  notes?: string;
}

// ============== ref.asset_substance (§11.3) ==============
export type ComponentRole =
  | 'main_component'
  | 'antibody'
  | 'linker'
  | 'payload'
  | 'excipient'
  | 'impurity';

export interface AssetSubstanceLink {
  component_role: ComponentRole;
  is_active_ingredient: boolean;
  notes?: string | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at?: string | null;
  asset_code: string;
  asset_internal_name: string;
  asset_type: string;
  asset_status: string;
  asset_phase: string;
  substance_code: string;
  substance_preferred_name: string;
  substance_status: string;
  substance_type: string;
}

export interface AssetSubstanceLinkCreatePayload {
  substance_code: string;
  component_role: ComponentRole;
  is_active_ingredient?: boolean;
  notes?: string;
}

// ============== ref.project_asset (§11.4) ==============
export type ProjectAssetRelationType =
  | 'primary'
  | 'supporting'
  | 'derivative'
  | 'reference';

export interface ProjectAssetLink {
  relation_type: string;
  notes?: string | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at?: string | null;
  project_code: string;
  project_name: string;
  project_status: string;
  project_type: string;
  asset_code: string;
  asset_internal_name: string;
  asset_type: string;
  asset_status: string;
  asset_phase: string;
}

export interface ProjectAssetLinkFromProjectPayload {
  asset_code: string;
  relation_type: ProjectAssetRelationType;
  notes?: string;
}

export interface ProjectAssetLinkFromAssetPayload {
  project_code: string;
  relation_type: ProjectAssetRelationType;
  notes?: string;
}

// ============== Asset (DM-MDM-001 §8) ==============
export type AssetType =
  | 'mab'
  | 'bispecific'
  | 'adc'
  | 'fusion'
  | 'small_molecule'
  | 'combination'
  | 'other';

export type AssetPhase =
  | 'discovery'
  | 'preclinical'
  | 'phase_1'
  | 'phase_2'
  | 'phase_3'
  | 'submission'
  | 'approved'
  | 'marketed'
  | 'discontinued';

export type AssetStatus = 'active' | 'on_hold' | 'terminated';

export interface AssetBrief {
  asset_code: string;
  internal_name: string;
  trade_name?: string | null;
  inn_name?: string | null;
  asset_type: AssetType;
  therapeutic_area?: string | null;
  current_phase: AssetPhase;
  status: AssetStatus;
  is_commercial: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssetDetail {
  asset_id: number;
  asset_code: string;
  internal_name: string;
  trade_name?: string | null;
  inn_name?: string | null;
  asset_type: AssetType;
  therapeutic_area?: string | null;
  indication?: string | null;
  dosage_form?: string | null;
  strength?: string | null;
  route_of_administration?: string | null;
  current_phase: AssetPhase;
  phase_change_at?: string | null;
  status: AssetStatus;
  is_commercial: boolean;
  first_approval_date?: string | null;
  first_launch_date?: string | null;
  description?: string | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
  version: number;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
}

export interface AssetListQuery {
  q?: string;
  asset_type?: string;
  current_phase?: string;
  status?: string;
  therapeutic_area?: string;
  is_commercial?: boolean;
  page?: number;
  page_size?: number;
  sort?: string;
}

export interface AssetCreatePayload {
  internal_name: string;
  trade_name?: string;
  inn_name?: string;
  asset_type: AssetType;
  therapeutic_area?: string;
  indication?: string;
  dosage_form?: string;
  strength?: string;
  route_of_administration?: string;
  current_phase?: AssetPhase;
  is_commercial?: boolean;
  first_approval_date?: string;
  first_launch_date?: string;
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export interface AssetUpdatePayload {
  version: number;
  change_reason?: string;
  internal_name?: string;
  trade_name?: string;
  inn_name?: string;
  asset_type?: AssetType;
  therapeutic_area?: string;
  indication?: string;
  dosage_form?: string;
  strength?: string;
  route_of_administration?: string;
  current_phase?: AssetPhase;
  is_commercial?: boolean;
  first_approval_date?: string;
  first_launch_date?: string;
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export type AssetAction = 'hold' | 'resume' | 'terminate';

export interface AssetStatusChangePayload {
  comment: string;
  // 仅 :terminate 是 GxP 关键动作必传 signature
  signature?: SignatureBlock;
}

// §8.3 asset_market_id
export type MarketIdStatus = 'pending' | 'approved' | 'withdrawn' | 'expired';

export interface AssetMarketId {
  market_id_pk: number;
  asset_id: number;
  market_code: string;
  id_type: string;
  id_value: string;
  issuing_authority?: string | null;
  application_date?: string | null;
  approval_date?: string | null;
  expiry_date?: string | null;
  status?: MarketIdStatus | null;
  notes?: string | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
}

export interface AssetMarketIdCreatePayload {
  market_code: string;
  id_type: string;
  id_value: string;
  issuing_authority?: string;
  application_date?: string;
  approval_date?: string;
  expiry_date?: string;
  status?: MarketIdStatus;
  notes?: string;
}

export interface AssetMarketIdUpdatePayload {
  change_reason?: string;
  market_code?: string;
  id_type?: string;
  id_value?: string;
  issuing_authority?: string;
  application_date?: string;
  approval_date?: string;
  expiry_date?: string;
  status?: MarketIdStatus;
  notes?: string;
}

// ============== 全局搜索 ==============
export type SearchEntityType = 'substance' | 'project' | 'asset';
export type SearchMatchedField =
  | 'code'
  | 'name'
  | 'name_en'
  | 'internal_code'
  | 'indication'
  | 'xref';

export interface SearchHit {
  entity_type: SearchEntityType;
  code: string;
  name: string;
  status?: string | null;
  matched_field: SearchMatchedField;
  sub_type?: string | null;
  snippet?: string | null;
}

// API-MDM-001 V1.1 §8.3 行 1688-1721 响应分组结构
export interface SearchGroup {
  total: number;
  items: SearchHit[];
}

export interface GlobalSearchResponse {
  query: string;
  total: number;
  results: {
    substance: SearchGroup;
    project: SearchGroup;
    asset: SearchGroup;
  };
}

// ============== Audit & status history ==============
export interface ChangeHistoryItem {
  field_name: string;
  old_value?: unknown;
  new_value?: unknown;
}

export interface AuditLogItem {
  log_id: number;
  user_id?: number | null;
  username: string;
  action: string;
  entity_schema?: string | null;
  entity_table?: string | null;
  entity_id?: number | null;
  entity_code?: string | null;
  reason?: string | null;
  ip_address?: string | null;
  request_id?: string | null;
  timestamp: string;
  changes: ChangeHistoryItem[];
}

export interface StatusHistoryItem {
  history_id: number;
  old_status?: string | null;
  new_status: string;
  change_reason: string;
  changed_at: string;
  changed_by: number;
  e_signature_id?: number | null;
}

// ============== 同一性判定 ==============
export interface CheckSamenessRequest {
  substance_type: SubstanceType;
  heavy_chain_sequence?: string;
  light_chain_sequence?: string;
  internal_code?: string;
  tolerance?: 'exact';
}

export interface SamenessMatch {
  substance_code: string;
  preferred_name: string;
  status: SubstanceStatus;
  substance_type: SubstanceType;
  matched_fields: string[];
  confidence: number;
}

export interface CheckSamenessResponse {
  matches: SamenessMatch[];
  input_summary: {
    heavy_chain_hash?: string | null;
    light_chain_hash?: string | null;
    internal_code?: string | null;
  };
}
