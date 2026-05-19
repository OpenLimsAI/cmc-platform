import type {
  MaterialBatchStatus,
  MaterialStatus,
  MaterialType,
} from '@/api/types';

export const MATERIAL_TYPE_OPTIONS: { value: MaterialType; label: string; color: string }[] = [
  { value: 'reagent', label: '试剂', color: 'blue' },
  { value: 'consumable', label: '耗材', color: 'green' },
  { value: 'standard', label: '标准品', color: 'gold' },
  { value: 'column', label: '色谱柱', color: 'purple' },
];

// grade 已改为自由文本，提供常用建议值
export const GRADE_SUGGESTIONS = [
  'RUO', 'GMP', 'AR', 'GR', 'CP', 'HPLC',
  'USP Reference Standard', 'Working Standard', 'ACS', 'Reagent Plus',
];

// 物料状态（主表 5 值，无状态机）
export const MATERIAL_STATUS_OPTIONS: { value: MaterialStatus; label: string }[] = [
  { value: 'active', label: '在用' },
  { value: 'quarantine', label: '隔离' },
  { value: 'released', label: '已放行' },
  { value: 'rejected', label: '不合格' },
  { value: 'retired', label: '已退役' },
];

// 批次状态（5 值）
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

// 物料分类（公司分类体系，15 值扁平枚举）
export const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: '一般耗材', label: '一般耗材' },
  { value: '关键耗材', label: '关键耗材' },
  { value: '关键试剂', label: '关键试剂' },
  { value: '内包材', label: '内包材' },
  { value: '外包材', label: '外包材' },
  { value: '劳保', label: '劳保' },
  { value: '原辅料', label: '原辅料' },
  { value: '参比品', label: '参比品' },
  { value: '对照品', label: '对照品' },
  { value: '工艺用水/气', label: '工艺用水/气' },
  { value: '标准品', label: '标准品' },
  { value: '细胞种子', label: '细胞种子' },
  { value: '自制包材', label: '自制包材' },
  { value: '试剂', label: '试剂' },
  { value: '运输包装材料', label: '运输包装材料' },
];

// 危化品分类（多选）
export const HAZARD_CLASS_OPTIONS = [
  { value: '危化品', label: '危化品' },
  { value: '易燃', label: '易燃' },
  { value: '易制毒', label: '易制毒' },
  { value: '易制爆', label: '易制爆' },
  { value: '剧毒品', label: '剧毒品' },
];

// 计量单位
export const UNIT_OPTIONS = [
  { value: 'ea', label: '个(ea)' },
  { value: '瓶', label: '瓶' },
  { value: '盒', label: '盒' },
  { value: '支', label: '支' },
  { value: '根', label: '根' },
  { value: '袋', label: '袋' },
  { value: '包', label: '包' },
  { value: '张', label: '张' },
  { value: '卷', label: '卷' },
  { value: '把', label: '把' },
  { value: 'kg', label: 'kg' },
  { value: 'g', label: 'g' },
  { value: 'mg', label: 'mg' },
  { value: 'L', label: 'L' },
  { value: 'mL', label: 'mL' },
];

// source_type 建议值
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
  'membrane',
  'gel',
];

// 常见存储条件
export const STORAGE_CONDITION_SUGGESTIONS = [
  '2-8°C',
  '-20°C',
  '-80°C',
  'RT (15-25°C)',
  '-150°C 气相液氮',
];
