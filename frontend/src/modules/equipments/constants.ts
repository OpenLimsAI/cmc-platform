import type { EquipmentCategory, EquipmentStatus } from '@/api/equipments';

export const EQUIPMENT_CATEGORY_OPTIONS: {
  value: EquipmentCategory;
  label: string;
  color: string;
  hint: string; // 建议定义 + 典型设备（下拉/表单提示用）
}[] = [
  {
    value: '分析仪器',
    label: '分析仪器',
    color: 'blue',
    hint: '用于产生检验、分析、表征数据的仪器。典型：HPLC/UPLC、GC、MS、CE、UV、酶标仪、Biacore、溶出仪',
  },
  {
    value: '工艺/制备设备',
    label: '工艺/制备设备',
    color: 'purple',
    hint: '直接用于研发、中试、生产或工艺开发操作的设备。典型：生物反应器、层析系统、TFF、配液罐、灌装设备、制剂设备',
  },
  {
    value: '通用实验室设备',
    label: '通用实验室设备',
    color: 'green',
    hint: '支持实验操作，但本身不直接定义为复杂分析系统。典型：离心机、天平、pH 计、移液器、培养箱、水浴、振荡器、显微镜',
  },
  {
    value: '公用工程/环境与支持系统',
    label: '公用工程/环境与支持系统',
    color: 'gold',
    hint: '提供水、气、环境、灭菌、低温保存等支持条件的系统。典型：纯化水/WFI、HVAC、压缩空气、洁净室、高压灭菌器、冰箱/超低温冰箱',
  },
  {
    value: 'IT/自动化与数据系统',
    label: 'IT/自动化与数据系统',
    color: 'cyan',
    hint: '独立的软件、服务器、网络、数据库、采集系统。典型：LIMS、ELN、服务器、数据库、网络设备、数据采集工作站',
  },
];

// 分类值常量（避免散落的魔法字符串）
export const IT_CATEGORY: EquipmentCategory = 'IT/自动化与数据系统';

// 工作站/本机硬件配置字段。group=identity 的三项对 IT 类设备复用主字段(生产商/型号/序列号)，
// IT 自动展开时只渲染 spec 子集；非 IT「附带专用工作站」时渲染全部。
export const WORKSTATION_FIELDS: {
  key: string;
  label: string;
  group: 'identity' | 'spec';
}[] = [
  { key: 'brand', label: '电脑品牌', group: 'identity' },
  { key: 'model', label: '电脑型号', group: 'identity' },
  { key: 'serial', label: '电脑序列号', group: 'identity' },
  { key: 'os', label: '操作系统', group: 'spec' },
  { key: 'cpu', label: 'CPU', group: 'spec' },
  { key: 'gpu', label: 'GPU', group: 'spec' },
  { key: 'ram', label: '内存', group: 'spec' },
  { key: 'disk', label: '硬盘', group: 'spec' },
  { key: 'monitor_brand', label: '显示器品牌', group: 'spec' },
  { key: 'monitor_model', label: '显示器型号', group: 'spec' },
  { key: 'monitor_serial', label: '显示器序列号', group: 'spec' },
];

export const EQUIPMENT_STATUS_OPTIONS: {
  value: EquipmentStatus;
  label: string;
  color: string;
}[] = [
  { value: 'active', label: '在册', color: 'success' },
  { value: 'retired', label: '已退役', color: 'default' },
];
