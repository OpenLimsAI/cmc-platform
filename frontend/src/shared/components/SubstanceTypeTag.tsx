import { Tag } from 'antd';
import type { SubstanceType } from '@/api/types';

const TYPE_MAP: Record<string, { text: string; color: string }> = {
  mab: { text: '单抗', color: 'blue' },
  bispecific: { text: '双抗', color: 'geekblue' },
  adc: { text: 'ADC', color: 'purple' },
  fusion: { text: '融合蛋白', color: 'cyan' },
  small_molecule: { text: '小分子', color: 'green' },
  oligonucleotide: { text: '寡核苷酸', color: 'orange' },
  other: { text: '其他', color: 'default' },
};

export function SubstanceTypeTag({ type }: { type: SubstanceType | string }) {
  const cfg = TYPE_MAP[type] ?? { text: type, color: 'default' };
  return <Tag color={cfg.color}>{cfg.text}</Tag>;
}
