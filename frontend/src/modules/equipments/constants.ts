import type { EquipmentCategory, EquipmentStatus } from '@/api/equipments';

export const EQUIPMENT_CATEGORY_OPTIONS: {
  value: EquipmentCategory;
  label: string;
  color: string;
}[] = [
  { value: '分析仪器', label: '分析仪器', color: 'blue' },
  { value: '实验设备', label: '实验设备', color: 'green' },
  { value: '辅助设备', label: '辅助设备', color: 'gold' },
  { value: '其他', label: '其他', color: 'default' },
];

export const EQUIPMENT_STATUS_OPTIONS: {
  value: EquipmentStatus;
  label: string;
  color: string;
}[] = [
  { value: 'active', label: '在册', color: 'success' },
  { value: 'retired', label: '已退役', color: 'default' },
];
