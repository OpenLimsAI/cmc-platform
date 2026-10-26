import type {
  AssetAction,
  AssetPhase,
  AssetStatus,
  AssetType,
  ComponentRole,
  MarketIdStatus,
  ProjectAssetRelationType,
} from '@/api/types';

// DM-MDM-001 §8.2 ck_asset_type
export const ASSET_TYPE_OPTIONS: { value: AssetType; label: string }[] = [
  { value: 'mab', label: '单抗' },
  { value: 'bispecific', label: '双抗' },
  { value: 'adc', label: 'ADC' },
  { value: 'fusion', label: '融合蛋白' },
  { value: 'small_molecule', label: '小分子' },
  { value: 'combination', label: '联合制剂' },
  { value: 'other', label: '其他' },
];

// §8.2 ck_asset_phase
export const ASSET_PHASE_OPTIONS: { value: AssetPhase; label: string; color: string }[] = [
  { value: 'discovery', label: '发现', color: 'default' },
  { value: 'preclinical', label: '临床前', color: 'blue' },
  { value: 'phase_1', label: 'I 期', color: 'blue' },
  { value: 'phase_2', label: 'II 期', color: 'cyan' },
  { value: 'phase_3', label: 'III 期', color: 'geekblue' },
  { value: 'submission', label: '申报中', color: 'purple' },
  { value: 'approved', label: '已批准', color: 'success' },
  { value: 'marketed', label: '已上市', color: 'success' },
  { value: 'discontinued', label: '已终止', color: 'error' },
];

// §8.2 asset.current_phase（业务进度）label 映射；与 ASSET_PHASE_OPTIONS 同源，按需展示
export const ASSET_PHASE_LABELS: Record<string, string> = {
  discovery: '发现',
  preclinical: '临床前',
  phase_1: 'I 期',
  phase_2: 'II 期',
  phase_3: 'III 期',
  submission: '申报中',
  approved: '已批准',
  marketed: '已上市',
  discontinued: '已终止',
};

// §8.2 ck_asset_status（3 值）
export const ASSET_STATUS_OPTIONS: { value: AssetStatus; label: string }[] = [
  { value: 'active', label: '活跃' },
  { value: 'on_hold', label: '暂停' },
  { value: 'terminated', label: '已终止' },
];

// ============== 状态机 ==============
export const AVAILABLE_ASSET_ACTIONS: Record<AssetStatus, AssetAction[]> = {
  active:     ['hold', 'terminate'],
  on_hold:    ['resume', 'terminate'],
  terminated: [],
};

// terminate 是 GxP 关键 → requiresSignature
export const ASSET_ACTION_LABELS: Record<
  AssetAction,
  { label: string; danger?: boolean; requiresSignature?: boolean }
> = {
  hold:      { label: '暂停', danger: true },
  resume:    { label: '恢复' },
  terminate: { label: '终止', danger: true, requiresSignature: true },
};

export const ASSET_STATUS_COLOR: Record<string, string> = {
  active: 'green',
  on_hold: 'orange',
  terminated: 'red',
};

// ============== 多市场注册号 ==============
export const MARKET_CODE_OPTIONS = [
  { value: 'CN', label: '中国 (NMPA)' },
  { value: 'US', label: '美国 (FDA)' },
  { value: 'EU', label: '欧盟 (EMA)' },
  { value: 'JP', label: '日本 (PMDA)' },
  { value: 'GLOBAL', label: '全球' },
];

export const MARKET_ID_TYPE_SUGGESTIONS = [
  'NDC',
  'NMPA_APPROVAL',
  'EMA_PROCEDURE',
  'PMDA',
  'OTHER',
];

export const MARKET_ID_STATUS_OPTIONS: { value: MarketIdStatus; label: string; color: string }[] = [
  { value: 'pending', label: '申请中', color: 'processing' },
  { value: 'approved', label: '已批准', color: 'success' },
  { value: 'withdrawn', label: '已撤回', color: 'default' },
  { value: 'expired', label: '已过期', color: 'error' },
];

// ============== ref.asset_substance (§11.3) ==============
export const COMPONENT_ROLE_OPTIONS: { value: ComponentRole; label: string; color: string }[] = [
  { value: 'main_component', label: '主成分', color: 'gold' },
  { value: 'antibody', label: '抗体', color: 'blue' },
  { value: 'linker', label: '连接子', color: 'cyan' },
  { value: 'payload', label: '载荷', color: 'purple' },
  { value: 'excipient', label: '辅料', color: 'default' },
  { value: 'impurity', label: '杂质', color: 'orange' },
];

// ============== ref.project_asset (§11.4) ==============
// 文档无 CHECK 枚举，前端给建议值
export const PROJECT_ASSET_RELATION_OPTIONS: {
  value: ProjectAssetRelationType;
  label: string;
  color: string;
}[] = [
  { value: 'primary', label: '主要', color: 'gold' },
  { value: 'supporting', label: '支撑', color: 'blue' },
  { value: 'derivative', label: '衍生', color: 'purple' },
  { value: 'reference', label: '参考', color: 'default' },
];
