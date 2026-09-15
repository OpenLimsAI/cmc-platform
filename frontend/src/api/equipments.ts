import { api, unwrap, unwrapList } from './client';

// ============== EQP 设备主数据类型 ==============
export type EquipmentCategory =
  | '分析仪器'
  | '工艺/制备设备'
  | '通用实验室设备'
  | '公用工程/环境与支持系统'
  | 'IT/自动化与数据系统';
export type EquipmentMasterStatus = 'active' | 'retired';
export type EquipmentStatus = 'enabled' | 'sealed' | 'scrapped';
// 设备分级：分析仪器 A/B/C（USP 口径）；其他分类 关键/一般
export type EquipmentCriticality = 'A' | 'B' | 'C' | '关键' | '一般';

export interface EquipmentBrief {
  equipment_code: string; // 设备ID（系统生成 EQP-）
  equipment_no: string | null; // 设备编号（业务/历史号）
  fixed_asset_no: string | null; // 固资编号
  equipment_name: string;
  equipment_name_en: string | null;
  /** 别名/曾用名（多个用 ; 分隔），来自设备部台账 */
  alias: string | null;
  category: EquipmentCategory;
  model: string | null;
  manufacturer: string | null;
  serial_no: string | null;
  department: string | null; // 使用部门
  site: string | null; // 厂区
  room: string | null; // 房间/存放位置
  criticality: EquipmentCriticality | null; // 设备分级
  status: EquipmentMasterStatus;
  equipment_status: EquipmentStatus;
  created_at: string;
  updated_at: string;
}

export interface WorkstationInfo {
  brand?: string | null;
  model?: string | null;
  serial?: string | null;
  os?: string | null;
  cpu?: string | null;
  gpu?: string | null;
  ram?: string | null;
  disk?: string | null;
  monitor_brand?: string | null;
  monitor_model?: string | null;
  monitor_serial?: string | null;
}

export interface EquipmentDetail extends EquipmentBrief {
  equipment_id: number;
  rated_power: string | null;
  origin: string | null;
  criticality_basis: string | null; // 分级依据
  commission_date: string | null; // 首次启用日期
  manufacture_date: string | null;
  asset_value: string | null;
  supplier: string | null;
  has_workstation: boolean;
  workstation_info: WorkstationInfo | null;
  description: string | null;
  notes: string | null;
  extra: Record<string, unknown> | null;
  created_by: number;
  updated_by: number;
  deleted_at: string | null;
  deleted_by: number | null;
}

export interface EquipmentCreatePayload {
  // 设备ID(equipment_code) 系统自动生成, 不提交
  equipment_no?: string | null; // 设备编号（业务/历史号）
  fixed_asset_no?: string | null; // 固资编号
  equipment_name: string;
  equipment_name_en?: string | null;
  alias?: string | null;
  category: EquipmentCategory;
  model?: string | null;
  manufacturer?: string | null;
  serial_no?: string | null;
  rated_power?: string | null;
  origin?: string | null;
  department?: string | null;
  site?: string | null;
  room?: string | null;
  criticality?: EquipmentCriticality | null;
  criticality_basis?: string | null;
  commission_date?: string | null;
  manufacture_date?: string | null;
  asset_value?: string | number | null;
  supplier?: string | null;
  has_workstation?: boolean;
  workstation_info?: WorkstationInfo | null;
  description?: string | null;
  notes?: string | null;
}

export interface EquipmentUpdatePayload extends Partial<Omit<EquipmentCreatePayload, 'equipment_code'>> {
  change_reason?: string;
  status?: EquipmentMasterStatus;
  equipment_status?: EquipmentStatus;
}

export interface EquipmentListQuery {
  q?: string;
  category?: string;
  status?: string;
  equipment_status?: string;
  manufacturer?: string;
  department?: string;
  site?: string;
  criticality?: string;
  page?: number;
  page_size?: number;
  sort?: string;
}

export const equipmentsApi = {
  list: (query: EquipmentListQuery = {}) =>
    unwrapList<EquipmentBrief>(api.get('/equipments', { params: query })),

  get: (code: string) =>
    unwrap<EquipmentDetail>(api.get(`/equipments/${encodeURIComponent(code)}`)),

  create: (payload: EquipmentCreatePayload) =>
    unwrap<EquipmentDetail>(api.post('/equipments', payload)),

  update: (code: string, payload: EquipmentUpdatePayload) =>
    unwrap<EquipmentDetail>(api.put(`/equipments/${encodeURIComponent(code)}`, payload)),

  delete: (code: string, change_reason: string) =>
    api.delete(`/equipments/${encodeURIComponent(code)}`, {
      data: { change_reason },
    }),
};
