import type {
  MoleculeTargetRole,
  SnapshotSource,
  TargetLocation,
  TargetStatus,
  TargetType,
} from '@/api/targets';
import type { StatusActionDef } from '@/shared/components/StatusActionsBar';

// 与后端 CHECK / Pydantic Literal 三份硬编码保持一致（决策 #6）
export const TARGET_TYPE_OPTIONS: { value: TargetType; label: string; color: string; hint: string }[] = [
  { value: '受体', label: '受体', color: 'blue', hint: '细胞表面/胞内受体，如 HER2、PD-1（也可按 CD 号归表面抗原）' },
  { value: '配体·细胞因子', label: '配体·细胞因子', color: 'purple', hint: '可溶性配体、细胞因子、生长因子，如 IL-23、TNF、VEGF' },
  { value: '表面抗原', label: '表面抗原', color: 'cyan', hint: '有 CD 编号的膜表面标志物，如 CD20、CD19、CD279(PD-1)' },
  { value: '酶', label: '酶', color: 'gold', hint: '有 EC 号或酶活性关键词，如凝血因子 IX/X、TOP1' },
  { value: '其他', label: '其他', color: 'default', hint: '以上都不适用' },
];

export const TARGET_LOCATION_OPTIONS: { value: TargetLocation; label: string; color: string; hint: string }[] = [
  { value: '膜型', label: '膜型', color: 'blue', hint: 'UniProt 定位含 membrane' },
  { value: '可溶型', label: '可溶型', color: 'green', hint: 'Secreted / extracellular' },
  { value: '两者都有', label: '两者都有', color: 'geekblue', hint: '膜结合前体 + 可溶形式（如 TNF）' },
  { value: '胞内', label: '胞内', color: 'default', hint: '仅胞质/核内（常见于 ADC 载荷靶点）' },
];

export const TARGET_STATUS_OPTIONS: { value: TargetStatus; label: string; color: string }[] = [
  { value: 'draft', label: '草稿', color: 'default' },
  { value: 'published', label: '已发布', color: 'success' },
  { value: 'retired', label: '已退役', color: 'warning' },
];

export const MOLECULE_TARGET_ROLE_OPTIONS: { value: MoleculeTargetRole; label: string; color: string }[] = [
  { value: 'antibody_target', label: '抗体结合靶点', color: 'blue' },
  { value: 'payload_target', label: '载荷作用靶点', color: 'orange' },
  { value: 'other', label: '其他', color: 'default' },
];

export const SNAPSHOT_SOURCE_LABELS: Record<SnapshotSource, string> = {
  uniprot: 'UniProt',
  chembl_target: 'ChEMBL target',
  chembl_molecule: 'ChEMBL molecule',
  chembl_mechanism: 'ChEMBL mechanism',
  other: '其他',
};

// 轻档审核：按当前状态可用的动作（无电签）
export const TARGET_AVAILABLE_ACTIONS: Record<TargetStatus, StatusActionDef[]> = {
  draft: [
    { action: 'publish', label: '发布' },
    { action: 'retire', label: '退役', danger: true },
  ],
  published: [{ action: 'retire', label: '退役', danger: true }],
  retired: [{ action: 'publish', label: '重新发布' }],
};
