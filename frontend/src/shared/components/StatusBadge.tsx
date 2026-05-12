import { Tag } from 'antd';
import type { TagProps } from 'antd';

type EntityType = 'substance' | 'project' | 'asset' | 'material';

interface StatusMapping {
  text: string;
  color: TagProps['color'];
}

const SUBSTANCE_STATUS: Record<string, StatusMapping> = {
  draft: { text: '草稿', color: 'default' },
  registered: { text: '已注册', color: 'blue' },
  active: { text: '活跃', color: 'success' },
  restricted: { text: '受限', color: 'warning' },
  deprecated: { text: '已弃用', color: 'error' },
  obsoleted: { text: '已废止', color: 'error' },
};

const PROJECT_STATUS: Record<string, StatusMapping> = {
  proposed: { text: '已提议', color: 'default' },
  initiated: { text: '已立项', color: 'blue' },
  active: { text: '进行中', color: 'success' },
  on_hold: { text: '暂停', color: 'warning' },
  completed: { text: '已完成', color: 'success' },
  terminated: { text: '已终止', color: 'error' },
};

// §8.2 asset.status 只有 3 值（管控状态）
const ASSET_STATUS: Record<string, StatusMapping> = {
  active: { text: '活跃', color: 'success' },
  on_hold: { text: '暂停', color: 'warning' },
  terminated: { text: '已终止', color: 'error' },
};

// §8.2 asset.current_phase（业务进度）；与 ASSET_PHASE 同表，按需展示
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

const MATERIAL_STATUS: Record<string, StatusMapping> = {
  in_stock: { text: '在库', color: 'success' },
  in_use: { text: '使用中', color: 'processing' },
  quarantine: { text: '隔离', color: 'warning' },
  expired: { text: '过期', color: 'error' },
  rejected: { text: '不合格', color: 'error' },
  disposed: { text: '已处置', color: 'default' },
};

const MAPPING: Record<EntityType, Record<string, StatusMapping>> = {
  substance: SUBSTANCE_STATUS,
  project: PROJECT_STATUS,
  asset: ASSET_STATUS,
  material: MATERIAL_STATUS,
};

interface StatusBadgeProps {
  type: EntityType;
  status: string;
}

export function StatusBadge({ type, status }: StatusBadgeProps) {
  const mapping = MAPPING[type]?.[status] ?? { text: status, color: 'default' };
  return <Tag color={mapping.color}>{mapping.text}</Tag>;
}
