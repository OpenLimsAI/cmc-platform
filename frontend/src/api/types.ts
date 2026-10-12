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
  force_password_change?: boolean;
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
  must_change_password?: boolean;
  roles: string[];
  permissions: string[];
}

// ============== Admin: 用户管理（API10）==============
export type UserStatus = 'active' | 'locked' | 'disabled';

export interface UserListItem {
  user_id: number;
  username: string;
  email: string;
  full_name: string;
  department?: string | null;
  title?: string | null;
  status: UserStatus;
  last_login_at?: string | null;
  created_at: string;
  roles: RoleBrief[];
}

export interface UserDetail {
  user_id: number;
  username: string;
  email: string;
  full_name: string;
  full_name_en?: string | null;
  department?: string | null;
  title?: string | null;
  phone?: string | null;
  status: UserStatus;
  failed_login_count: number;
  locked_at?: string | null;
  last_login_at?: string | null;
  password_changed_at?: string | null;
  password_expires_at?: string | null;
  force_password_change: boolean;
  mfa_enabled: boolean;
  created_at: string;
  created_by?: number | null;
  updated_at: string;
  updated_by?: number | null;
  roles: RoleBrief[];
  permissions: string[];
}

export interface UserCreatePayload {
  username: string;
  email: string;
  password: string;
  full_name: string;
  full_name_en?: string | null;
  department?: string | null;
  title?: string | null;
  phone?: string | null;
  role_codes: string[];
}

export interface UserUpdatePayload {
  email?: string;
  full_name?: string;
  full_name_en?: string | null;
  department?: string | null;
  title?: string | null;
  phone?: string | null;
}

export interface UserListQuery {
  q?: string;
  role_code?: string;
  /** 部门：包含匹配、不分大小写（输入 TT 可命中 TT1/TT5/TT7） */
  department?: string;
  status?: UserStatus;
  page?: number;
  page_size?: number;
}

export interface ResetPasswordResult {
  username: string;
  temp_password: string;
  force_password_change: boolean;
}

// ============== Admin: 会话策略（2026-09-04；migration 0054）==============
export interface SessionPolicy {
  access_token_minutes: number;
  idle_timeout_minutes: number;
  absolute_max_hours: number;
  display_mode_idle_minutes: number;
  updated_at: string | null;
  /** 各字段允许范围 [min, max]，来自后端 LIMITS */
  limits: Record<string, [number, number]>;
}

export interface SessionPolicyUpdatePayload {
  access_token_minutes: number;
  idle_timeout_minutes: number;
  absolute_max_hours: number;
  display_mode_idle_minutes: number;
  reason?: string | null;
}

// ============== Admin: 部门管理员下放角色白名单（2026-09-10；migration 0055）==============
export interface DeptAdminPolicy {
  /** 部门管理员可挂/摘的角色码前缀，如 ['QV_'] */
  delegable_role_prefixes: string[];
  /** 永不可下放的角色（SYS_ADMIN / DEPT_ADMIN），后端常量 */
  protected_roles: string[];
  updated_at: string | null;
}

export interface DeptAdminPolicyUpdatePayload {
  delegable_role_prefixes: string[];
  reason?: string | null;
}

/** GET /auth/session-policy：当前用户生效值（展示模式账号 idle 已放宽） */
export interface MySessionPolicy {
  access_token_minutes: number;
  idle_timeout_minutes: number;
  absolute_max_hours: number;
  display_mode: boolean;
}

// ============== Admin: 角色与权限（M5.2）==============
export interface PermissionItem {
  permission_id: number;
  permission_code: string;
  resource: string;
  action: string;
  description?: string | null;
  is_system: boolean;
}

export interface RoleListItem {
  role_id: number;
  role_code: string;
  role_name: string;
  description?: string | null;
  is_system: boolean;
  permission_count: number;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface RoleDetail {
  role_id: number;
  role_code: string;
  role_name: string;
  description?: string | null;
  is_system: boolean;
  permission_count: number;
  user_count: number;
  permissions: PermissionItem[];
  created_at: string;
  updated_at: string;
}

export interface RoleCreatePayload {
  role_code: string;
  role_name: string;
  description?: string | null;
  permission_codes: string[];
}

export interface RoleUpdatePayload {
  role_name?: string;
  description?: string | null;
  permission_codes?: string[];
}

// ============== Admin: 全局审计 + 签名（M5.3）==============
export interface AuditLogQuery {
  q?: string;
  username?: string;
  action?: string;
  entity_table?: string;
  entity_code?: string;
  date_from?: string;  // ISO datetime
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface SignatureItem {
  signature_id: number;
  user_id: number;
  username: string;
  full_name: string;
  entity_schema: string;
  entity_table: string;
  entity_id: number;
  entity_code?: string | null;
  signature_meaning: string;
  signature_reason: string;
  signed_content_hash: string;
  signature_hash: string;
  signed_at: string;
}

export interface SignatureQuery {
  username?: string;
  entity_table?: string;
  entity_code?: string;
  signature_meaning?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

// ============== Dashboard (Phase 5.B) ==============
export interface DistributionItem {
  key: string | null;
  count: number;
}

export interface TrendPoint {
  date: string;
  count: number;
}

export type DashboardDomain = 'substance' | 'project' | 'asset' | 'material' | 'equipment' | 'target';

/** 2026-09-10 起按读权限裁剪：只含用户能进的域，缺的键就是没权限 */
export interface DashboardSummary {
  visible_domains: DashboardDomain[];
  totals: Partial<Record<DashboardDomain, number>>;
  distributions: Partial<{
    substance_by_type: DistributionItem[];
    substance_by_status: DistributionItem[];
    project_by_status: DistributionItem[];
    project_by_priority: DistributionItem[];
    asset_by_phase: DistributionItem[];
    asset_by_status: DistributionItem[];
    material_by_type: DistributionItem[];
    material_by_grade: DistributionItem[];
    equipment_by_category: DistributionItem[];
    equipment_by_status: DistributionItem[];
    target_by_status: DistributionItem[];
    target_by_entry_type: DistributionItem[];
  }>;
  trend_30d: Partial<Record<DashboardDomain, TrendPoint[]>>;
}

export interface GanttMilestone {
  milestone_id: number;
  milestone_name: string;
  planned_date: string | null;
  actual_date: string | null;
  status: string;
}

export interface GanttProject {
  project_code: string;
  project_name: string;
  status: string;
  priority?: string | null;
  planned_start_date: string | null;
  planned_end_date: string | null;
  actual_start_date: string | null;
  actual_end_date: string | null;
  milestones: GanttMilestone[];
}

// ============== Profile (M5.4) ==============
export interface LoginHistoryItem {
  login_id: number;
  username_input: string;
  success: boolean;
  failure_reason?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  login_at: string;
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
  extra?: Record<string, unknown>;
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

// ============== Project (SMP-RD-NUM-001 V2.1 §7.4c) ==============
export type ProjectType =
  | 'discovery'
  | 'nonclinical'
  | 'cmc'
  | 'clinical'
  | 'regulatory'
  | 'translational'
  | 'mixed';

// SMP V2.1 §10.3 project_phase 受控枚举（migration 0048）
export type ProjectPhase =
  | 'discovery'
  | 'lead_opt'
  | 'ind_enabling'
  | 'p1'
  | 'p2'
  | 'p3'
  | 'filed'
  | 'post_marketing';

// SMP V2.1 §7.4(a) 是否关联资产
export type ProjectCategory = 'asset_related' | 'non_asset';

// SMP V2.1 §7.4(b) portfolio 性质
export type ProjectNature =
  | 'nme'
  | 'indication_expansion'
  | 'geographic_expansion'
  | 'lcm'
  | 'regulatory_commitment'
  | 'cmc_change'
  | 'bd_evaluation'
  | 'platform'
  | 'discovery';

// SMP V2.1 §10.3 受控归属
export type OwningFunction =
  | 'rd'
  | 'clinical'
  | 'cmc'
  | 'regulatory'
  | 'qa'
  | 'it'
  | 'bd'
  | 'finance'
  | 'pmo'
  | 'other';

// SMP V2.1 §7A 上市后变更级别
export type RegulatoryChangeLevel = 'minor' | 'moderate' | 'major';

// SMP V2.1 §11.4-11.6 项目关系类型
export type ProjectRelationshipType =
  | 'merged_into'
  | 'split_from'
  | 'derived_from'
  | 'depends_on'
  | 'blocks';

export interface ProjectRelationshipItem {
  relationship_id: number;
  relationship_type: ProjectRelationshipType;
  direction: 'outgoing' | 'incoming';
  other_project_code: string;
  other_project_name: string;
  notes?: string | null;
  created_at: string;
}

export interface ProjectRelationshipCreatePayload {
  to_project_code: string;
  relationship_type: ProjectRelationshipType;
  notes?: string;
}

export type ProjectStatus =
  | 'proposed'
  | 'initiated'
  | 'active'
  | 'on_hold'
  | 'completed'
  | 'terminated'
  | 'cancelled';

export type ProjectPriority = 'high' | 'medium' | 'low';

export interface ProjectBrief {
  project_code: string;
  project_name: string;
  project_name_en?: string | null;
  project_type: ProjectType;
  project_phase?: ProjectPhase | null;
  project_category: ProjectCategory;
  project_nature: ProjectNature;
  owning_function: OwningFunction;
  asset_id?: number | null;
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
  project_phase?: ProjectPhase | null;
  project_category: ProjectCategory;
  project_nature: ProjectNature;
  owning_function: OwningFunction;
  participating_functions?: OwningFunction[] | null;
  asset_id?: number | null;
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
  approval_date?: string | null;
  approval_reference?: string | null;
  approval_year?: number | null;
  governance_approval_ref?: string | null;
  status_reason?: string | null;
  sap_wbs_mapping?: string | null;
  external_contract_refs?: string[] | null;
  partner_reference?: string | null;
  regulatory_change_level?: RegulatoryChangeLevel | null;
  pre_approval_required?: boolean | null;
  comparability_study_ref?: string | null;
  regulatory_submission_refs?: string[] | null;
  legacy_project_id?: string | null;
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
  project_category?: string;
  project_nature?: string;
  owning_function?: string;
  asset_id?: number;
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
  project_phase?: ProjectPhase;
  project_category?: ProjectCategory;
  project_nature?: ProjectNature;
  owning_function?: OwningFunction;
  participating_functions?: OwningFunction[];
  asset_id?: number;
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
  approval_reference?: string;
  governance_approval_ref?: string;
  status_reason?: string;
  sap_wbs_mapping?: string;
  external_contract_refs?: string[];
  partner_reference?: string;
  regulatory_change_level?: RegulatoryChangeLevel;
  pre_approval_required?: boolean;
  comparability_study_ref?: string;
  regulatory_submission_refs?: string[];
  legacy_project_id?: string;
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
  project_phase?: ProjectPhase;
  project_category?: ProjectCategory;
  project_nature?: ProjectNature;
  owning_function?: OwningFunction;
  participating_functions?: OwningFunction[];
  asset_id?: number;
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
  approval_reference?: string;
  governance_approval_ref?: string;
  status_reason?: string;
  sap_wbs_mapping?: string;
  external_contract_refs?: string[];
  partner_reference?: string;
  regulatory_change_level?: RegulatoryChangeLevel;
  pre_approval_required?: boolean;
  comparability_study_ref?: string;
  regulatory_submission_refs?: string[];
  legacy_project_id?: string;
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
  | 'terminate'
  | 'cancel';

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
  asset_id: number;
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
export type SearchEntityType =
  | 'substance'
  | 'project'
  | 'asset'
  | 'material'
  | 'equipment'
  | 'target';
export type SearchMatchedField =
  | 'code'
  | 'name'
  | 'name_en'
  | 'internal_code'
  | 'indication'
  | 'xref'
  | 'trade_name'
  | 'inn_name'
  | 'objective'
  | 'source_name'
  | 'model'
  | 'manufacturer'
  | 'serial_no'
  | 'equipment_no'
  | 'fixed_asset_no'
  | 'uniprot_id'
  | 'gene_symbol'
  | 'cd_antigen'
  | 'alias';

export interface SearchHit {
  entity_type: SearchEntityType;
  code: string;
  name: string;
  status?: string | null;
  matched_field: SearchMatchedField;
  sub_type?: string | null;
  snippet?: string | null;
}

// API-MDM-001 V1.1 §8.3 行 1688-1721 响应分组结构（M4.4 起含 material）
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
    material: SearchGroup;
    equipment: SearchGroup;
    target: SearchGroup;
  };
}

// ============== Material ==============
export type MaterialType = 'reagent' | 'consumable' | 'standard' | 'column';

export type MaterialStatus =
  | 'active'
  | 'quarantine'
  | 'released'
  | 'rejected'
  | 'retired';

export interface MaterialBrief {
  material_code: string;
  material_name: string;
  material_name_en?: string | null;
  material_type: MaterialType;
  category?: string | null;
  grade?: string | null;
  status: MaterialStatus;
  unit?: string | null;
  manufacturer?: string | null;
  spec_model?: string | null;
  physical_form?: string | null;
  source_name?: string | null;
  substance_id?: number | null;
  substance_code?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialDetail {
  material_id: number;
  material_code: string;
  material_name: string;
  material_name_en?: string | null;
  material_type: MaterialType;
  category?: string | null;
  substance_id?: number | null;
  substance_code?: string | null;
  manufacturer?: string | null;
  catalog_no?: string | null;
  spec_model?: string | null;
  unit: string;
  package_spec?: string | null;
  hazard_class?: string[] | null;
  physical_form?: string | null;
  storage_condition?: string | null;
  source_type?: string | null;
  source_name?: string | null;
  grade?: string | null;
  status: MaterialStatus;
  description?: string | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at?: string | null;
  deleted_by?: number | null;
}

export interface MaterialListQuery {
  q?: string;
  material_type?: string;
  category?: string;
  status?: string;
  grade?: string;
  substance_code?: string;
  source_type?: string;
  page?: number;
  page_size?: number;
  sort?: string;
}

export interface MaterialCreatePayload {
  material_code: string;
  material_name: string;
  material_name_en?: string;
  material_type: MaterialType;
  category?: string;
  substance_id?: number;
  substance_code?: string;
  manufacturer?: string;
  catalog_no?: string;
  spec_model?: string;
  unit?: string;
  package_spec?: string;
  hazard_class?: string[];
  physical_form?: string;
  storage_condition?: string;
  source_type?: string;
  source_name?: string;
  grade?: string;
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export interface MaterialUpdatePayload {
  change_reason?: string;
  material_name?: string;
  material_name_en?: string;
  material_type?: MaterialType;
  category?: string | null;
  substance_id?: number | null;
  substance_code?: string | null;
  manufacturer?: string | null;
  catalog_no?: string | null;
  spec_model?: string | null;
  unit?: string;
  package_spec?: string | null;
  hazard_class?: string[] | null;
  physical_form?: string;
  storage_condition?: string;
  source_type?: string;
  source_name?: string;
  grade?: string;
  status?: MaterialStatus;
  description?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

// material_batch (§10.2)
export type MaterialBatchStatus =
  | 'in_stock'
  | 'in_use'
  | 'depleted'
  | 'expired'
  | 'recalled';

export interface MaterialBatch {
  batch_id: number;
  material_id: number;
  batch_number: string;
  quantity_value?: string | null;
  quantity_unit?: string | null;
  manufacture_date?: string | null;
  expiry_date?: string | null;
  receive_date?: string | null;
  status: MaterialBatchStatus;
  source_batch_ref?: string | null;
  coa_url?: string | null;
  storage_location?: string | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
  created_by: number;
  updated_at: string;
  updated_by: number;
  deleted_at?: string | null;
  deleted_by?: number | null;
}

export interface MaterialBatchCreatePayload {
  batch_number: string;
  quantity_value?: string | number;
  quantity_unit?: string;
  manufacture_date?: string;
  expiry_date?: string;
  receive_date?: string;
  source_batch_ref?: string;
  coa_url?: string;
  storage_location?: string;
  notes?: string;
  extra?: Record<string, unknown>;
}

export interface MaterialBatchUpdatePayload {
  change_reason?: string;
  batch_number?: string;
  quantity_value?: string | number;
  quantity_unit?: string;
  manufacture_date?: string;
  expiry_date?: string;
  receive_date?: string;
  status?: MaterialBatchStatus;
  source_batch_ref?: string;
  coa_url?: string;
  storage_location?: string;
  notes?: string;
  extra?: Record<string, unknown>;
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
  full_name?: string | null;
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
