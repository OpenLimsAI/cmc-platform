import type {
  MaterialBatchStatus,
  MaterialGrade,
  MaterialStatus,
  MaterialType,
} from '@/api/types';

// DM-MDM-001 §10.1 ck_material_type
export const MATERIAL_TYPE_OPTIONS: { value: MaterialType; label: string; color: string }[] = [
  { value: 'candidate', label: '候选物', color: 'gold' },
  { value: 'reference', label: '参比品', color: 'blue' },
  { value: 'stability', label: '稳定性样品', color: 'cyan' },
  { value: 'buffer', label: '缓冲液', color: 'geekblue' },
  { value: 'raw', label: '原材料', color: 'default' },
  { value: 'intermediate', label: '中间体', color: 'purple' },
  { value: 'other', label: '其他', color: 'default' },
];

// §10.1 ck_material_grade（可空，4 值）
export const MATERIAL_GRADE_OPTIONS: { value: MaterialGrade; label: string; color: string }[] = [
  { value: 'RUO', label: 'RUO（研究专用）', color: 'default' },
  { value: 'GMP', label: 'GMP', color: 'success' },
  { value: 'Reference Standard', label: '参考标准品', color: 'gold' },
  { value: 'Working Standard', label: '工作标准品', color: 'blue' },
];

// §10.1 ck_material_status（主表 5 值，无状态机）
export const MATERIAL_STATUS_OPTIONS: { value: MaterialStatus; label: string }[] = [
  { value: 'active', label: '在用' },
  { value: 'quarantine', label: '隔离' },
  { value: 'released', label: '已放行' },
  { value: 'rejected', label: '不合格' },
  { value: 'retired', label: '已退役' },
];

// §10.2 ck_material_batch_status（5 值）
export const MATERIAL_BATCH_STATUS_OPTIONS: {
  value: MaterialBatchStatus;
  label: string;
  color: string;
}[] = [
  { value: 'in_stock', label: '在库', color: 'success' },
  { value: 'in_use', label: '使用中', color: 'processing' },
  { value: 'depleted', label: '已耗尽', color: 'default' },
  { value: 'expired', label: '过期', color: 'error' },
  { value: 'recalled', label: '召回', color: 'error' },
];

// source_type 字典（非 DB CHECK，前端建议值）
export const SOURCE_TYPE_OPTIONS = [
  { value: 'internal', label: '内部产出' },
  { value: 'cdmo', label: 'CDMO 委外' },
  { value: 'vendor', label: '外购' },
];

// 常见物理形态
export const PHYSICAL_FORM_SUGGESTIONS = [
  'liquid',
  'lyophilized',
  'powder',
  'crystal',
  'solution',
];

// 常见存储条件
export const STORAGE_CONDITION_SUGGESTIONS = [
  '2-8°C',
  '-20°C',
  '-80°C',
  'RT (15-25°C)',
  '-150°C 气相液氮',
];
