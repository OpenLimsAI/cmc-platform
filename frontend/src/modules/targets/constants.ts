import type { MoleculeTargetRole, SnapshotSource, TargetStatus } from '@/api/targets';
import type { StatusActionDef } from '@/shared/components/StatusActionsBar';

// UniProt 关键词类别（展示顺序 + 中文标签）；其余类别归"其他"
export const KEYWORD_CATEGORY_LABELS: Record<string, string> = {
  'Molecular function': '分子功能',
  'Cellular component': '细胞组分',
  'Biological process': '生物过程',
  Ligand: '配体',
  Domain: '结构域',
  PTM: '翻译后修饰',
  Disease: '疾病',
  'Technical term': '技术标签',
  'Coding sequence diversity': '编码序列多样性',
  'Developmental stage': '发育阶段',
};
export const KEYWORD_CATEGORY_ORDER = ['Molecular function', 'Cellular component', 'Biological process', 'Ligand', 'Domain', 'PTM', 'Disease'];

// 列表筛选用的常见 UniProt 分子功能关键词（下拉可输任意词，这里只是快捷项）
export const COMMON_MF_KEYWORDS = ['Receptor', 'Cytokine', 'Chemokine', 'Growth factor', 'Hormone', 'Kinase', 'Hydrolase', 'Protease', 'Transferase', 'Ion channel', 'Transducer'];
export const COMMON_LOCATIONS = ['Cell membrane', 'Secreted', 'Membrane', 'Cytoplasm', 'Nucleus', 'Endoplasmic reticulum', 'Golgi apparatus', 'Lysosome', 'Mitochondrion'];
export const ENTRY_TYPE_OPTIONS = [
  { value: 'Swiss-Prot', label: 'Swiss-Prot（人工审阅）' },
  { value: 'TrEMBL', label: 'TrEMBL（自动注释）' },
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
