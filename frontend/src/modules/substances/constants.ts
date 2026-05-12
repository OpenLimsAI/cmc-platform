import type { SubstanceAction, SubstanceStatus, SubstanceType, XrefType } from '@/api/types';

export const SUBSTANCE_TYPE_OPTIONS: { value: SubstanceType; label: string }[] = [
  { value: 'mab', label: '单抗 (mAb)' },
  { value: 'bispecific', label: '双抗' },
  { value: 'adc', label: 'ADC' },
  { value: 'fusion', label: '融合蛋白' },
  { value: 'small_molecule', label: '小分子' },
  { value: 'oligonucleotide', label: '寡核苷酸' },
  { value: 'other', label: '其他' },
];

export const XREF_TYPE_OPTIONS: { value: XrefType; label: string }[] = [
  { value: 'INN', label: 'INN' },
  { value: 'USAN', label: 'USAN' },
  { value: 'CAS', label: 'CAS' },
  { value: 'UNII', label: 'UNII' },
  { value: 'GSRS_UUID', label: 'GSRS UUID' },
  { value: 'ChEMBL', label: 'ChEMBL' },
  { value: 'DRUGBANK', label: 'DrugBank' },
  { value: 'TRADE_NAME', label: '商品名' },
  { value: 'GENERIC_NAME', label: '通用名' },
  { value: 'HISTORICAL_CODE', label: '历史编码' },
  { value: 'PROJECT_CODE', label: '项目编码' },
  { value: 'OTHER', label: '其他' },
];

export const ISOTYPE_OPTIONS = ['IgG1', 'IgG2', 'IgG3', 'IgG4', 'IgA', 'IgM', 'IgE'];

export const EXPRESSION_SYSTEM_OPTIONS = [
  'CHO-K1',
  'CHO-DG44',
  'CHO-S',
  'HEK293',
  'HEK293F',
  'NS0',
  'Sp2/0',
  'E.coli',
  'Pichia pastoris',
];

export const PROTEIN_TYPES: SubstanceType[] = ['mab', 'bispecific', 'fusion'];

export const cleanedSequenceLength = (seq?: string): number => {
  if (!seq) return 0;
  return seq.toUpperCase().replace(/[^A-Z]/g, '').length;
};

// 状态机可用动作：当前 status → 可执行的 action 列表
// 与 backend STATE_MACHINE 对齐（services.py）
export const AVAILABLE_ACTIONS: Record<SubstanceStatus, SubstanceAction[]> = {
  draft: ['approve'],
  registered: ['activate'],
  active: ['restrict', 'deprecate'],
  restricted: ['deprecate'],
  deprecated: ['obsolete'],
  obsoleted: [],
};

// GxP 关键动作要求电子签名（与 backend SIGNATURE_REQUIRED_ACTIONS 对齐）
export const ACTION_LABELS: Record<
  SubstanceAction,
  { label: string; danger?: boolean; requiresSignature?: boolean }
> = {
  approve: { label: '审核通过', requiresSignature: true },
  activate: { label: '激活', requiresSignature: true },
  restrict: { label: '限制访问', danger: true },
  deprecate: { label: '弃用', danger: true, requiresSignature: true },
  obsolete: { label: '废弃', danger: true, requiresSignature: true },
};
