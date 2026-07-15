import type {
  MilestoneStatus,
  MilestoneType,
  OwningFunction,
  ProjectAction,
  ProjectCategory,
  ProjectNature,
  ProjectPhase,
  ProjectStatus,
  ProjectType,
  RelationType,
} from '@/api/types';

// SMP-RD-NUM-001 V2.1 §7.4(c) 执行类型
export const PROJECT_TYPE_OPTIONS: { value: ProjectType; label: string }[] = [
  { value: 'discovery', label: '发现' },
  { value: 'nonclinical', label: '非临床' },
  { value: 'cmc', label: 'CMC 开发' },
  { value: 'clinical', label: '临床' },
  { value: 'regulatory', label: '注册' },
  { value: 'translational', label: '转化' },
  { value: 'mixed', label: '混合' },
];

// SMP V2.1 §10.3 project_phase 受控枚举
export const PROJECT_PHASE_OPTIONS: { value: ProjectPhase; label: string }[] = [
  { value: 'discovery', label: '发现' },
  { value: 'lead_opt', label: '先导优化' },
  { value: 'ind_enabling', label: 'IND 使能' },
  { value: 'p1', label: 'I 期' },
  { value: 'p2', label: 'II 期' },
  { value: 'p3', label: 'III 期' },
  { value: 'filed', label: '已申报' },
  { value: 'post_marketing', label: '上市后' },
];

// SMP V2.1 §7.4(a) 是否关联资产
export const PROJECT_CATEGORY_OPTIONS: { value: ProjectCategory; label: string }[] = [
  { value: 'asset_related', label: '资产相关' },
  { value: 'non_asset', label: '非资产' },
];

// SMP V2.1 §7.4(b) portfolio 性质
export const PROJECT_NATURE_OPTIONS: { value: ProjectNature; label: string }[] = [
  { value: 'nme', label: '新分子实体' },
  { value: 'indication_expansion', label: '适应症拓展' },
  { value: 'geographic_expansion', label: '地区拓展' },
  { value: 'lcm', label: '生命周期管理' },
  { value: 'regulatory_commitment', label: '监管承诺' },
  { value: 'cmc_change', label: 'CMC 变更' },
  { value: 'bd_evaluation', label: 'BD 评估' },
  { value: 'platform', label: '平台能力' },
  { value: 'discovery', label: '发现' },
];

// SMP V2.1 §10.3 受控归属
export const OWNING_FUNCTION_OPTIONS: { value: OwningFunction; label: string }[] = [
  { value: 'rd', label: '研发' },
  { value: 'clinical', label: '临床' },
  { value: 'cmc', label: 'CMC' },
  { value: 'regulatory', label: '注册' },
  { value: 'qa', label: '质量' },
  { value: 'it', label: 'IT' },
  { value: 'bd', label: '商务拓展' },
  { value: 'finance', label: '财务' },
  { value: 'pmo', label: 'PMO' },
  { value: 'other', label: '其他' },
];

// SMP V2.1 §11.3 status（补 cancelled）
export const PROJECT_STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: 'proposed', label: '已提议' },
  { value: 'initiated', label: '已立项' },
  { value: 'active', label: '进行中' },
  { value: 'on_hold', label: '暂停' },
  { value: 'completed', label: '已完成' },
  { value: 'terminated', label: '已终止' },
  { value: 'cancelled', label: '已取消' },
];

// UI10：V1.1 §7.2 / §9.2 项目优先级 + 保密等级（Batch F 后端已暴露）
export const PROJECT_PRIORITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'critical', label: '紧急' },
];

export const PROJECT_CONFIDENTIALITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'public', label: '公开' },
  { value: 'internal', label: '内部' },
  { value: 'restricted', label: '受限' },
];

// ============== 状态机 ==============
// 与 backend STATE_MACHINE 对齐（prs/services.py）
export const AVAILABLE_PROJECT_ACTIONS: Record<ProjectStatus, ProjectAction[]> = {
  proposed:   ['approve', 'cancel', 'terminate'],
  initiated:  ['start', 'cancel', 'terminate'],
  active:     ['hold', 'complete', 'terminate'],
  on_hold:    ['resume', 'terminate'],
  completed:  [],
  terminated: [],
  cancelled:  [],
};

// GxP 关键动作要求电子签名（与 backend SIGNATURE_REQUIRED_ACTIONS 对齐）
export const PROJECT_ACTION_LABELS: Record<
  ProjectAction,
  { label: string; danger?: boolean; requiresSignature?: boolean }
> = {
  approve:   { label: '审批立项', requiresSignature: true },
  start:     { label: '启动' },
  hold:      { label: '暂停', danger: true },
  resume:    { label: '恢复' },
  complete:  { label: '完成', requiresSignature: true },
  terminate: { label: '终止', danger: true, requiresSignature: true },
  cancel:    { label: '取消立项', danger: true, requiresSignature: true },
};

export const PROJECT_STATUS_COLOR: Record<string, string> = {
  proposed: 'gray',
  initiated: 'blue',
  active: 'green',
  on_hold: 'orange',
  completed: 'green',
  terminated: 'red',
  cancelled: 'gray',
};

// ============== 里程碑 (DM-MDM-001 §9.3) ==============
export const MILESTONE_TYPE_OPTIONS: { value: MilestoneType; label: string }[] = [
  { value: 'gate', label: '阶段门' },
  { value: 'deliverable', label: '交付物' },
  { value: 'decision', label: '决策点' },
];

export const MILESTONE_STATUS_OPTIONS: { value: MilestoneStatus; label: string; color: string }[] = [
  { value: 'planned', label: '已计划', color: 'default' },
  { value: 'in_progress', label: '进行中', color: 'processing' },
  { value: 'completed', label: '已完成', color: 'success' },
  { value: 'delayed', label: '延期', color: 'warning' },
  { value: 'cancelled', label: '已取消', color: 'default' },
];

// ============== 团队 (DM-MDM-001 §9.4) ==============
// role 是任意字符串，建议值供前端下拉，但允许自由输入
export const TEAM_ROLE_SUGGESTIONS: string[] = [
  'PM',
  'CMC Lead',
  'QA Lead',
  'Regulatory Lead',
  'Clinical Lead',
  'Research',
  'Member',
  'Observer',
];

// ============== ref.project_substance (DM-MDM-001 §11.2) ==============
export const RELATION_TYPE_OPTIONS: { value: RelationType; label: string; color: string }[] = [
  { value: 'primary', label: '主要', color: 'gold' },
  { value: 'secondary', label: '次要', color: 'blue' },
  { value: 'reference', label: '参考', color: 'default' },
  { value: 'control', label: '对照', color: 'cyan' },
  { value: 'derivative', label: '衍生', color: 'purple' },
];
