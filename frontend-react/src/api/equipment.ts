import client from "./client";

// ---------------------------------------------------------------------------
// 类型
// ---------------------------------------------------------------------------
export interface Equipment {
  equipment_id: number;
  equipment_code: string;
  equipment_no: string | null;
  fixed_asset_no: string | null;
  name: string;
  name_en: string | null;
  category: string;
  model: string | null;
  manufacturer: string | null;
  serial_no: string | null;
  rated_power: string | null;
  origin: string | null;
  supplier: string | null;
  has_workstation: boolean;
  workstation_info: Record<string, unknown> | null;
  mdm_status: string | null;
  mdm_synced_at: string | null;
  location_room: string | null;
  location_detail: string | null;
  responsible_person: string | null;
  status: string;
  purchase_date: string | null;
  commission_date: string | null;
  asset_value: number | null;
  remark: string | null;
  mdm_equipment_id: number | null;
  data_source: string;
  is_active: boolean;
  deactivated_at: string | null;
  deactivated_by: string | null;
  deactivate_reason: string | null;
  created_at: string;
  created_by: string | null;
  updated_at: string;
  updated_by: string | null;
}

export interface EquipmentPayload {
  equipment_code?: string;
  name: string;
  category: string;
  model?: string | null;
  manufacturer?: string | null;
  serial_no?: string | null;
  location_room?: string | null;
  location_detail?: string | null;
  responsible_person?: string | null;
  status?: string;
  purchase_date?: string | null;
  commission_date?: string | null;
  asset_value?: number | null;
  remark?: string | null;
}

export interface Calibration {
  calibration_id: number;
  equipment_id: number;
  calibration_date: string;
  calibration_agency: string | null;
  result: string;
  certificate_no: string | null;
  next_calibration_date: string | null;
  remark: string | null;
  created_at: string;
  created_by: string | null;
}

export interface Maintenance {
  maintenance_id: number;
  equipment_id: number;
  maintenance_date: string;
  maintenance_type: string;
  content: string | null;
  performed_by: string;
  next_maintenance_date: string | null;
  remark: string | null;
  created_at: string;
  created_by: string | null;
}

export interface Repair {
  repair_id: number;
  equipment_id: number;
  report_date: string;
  fault_description: string;
  repair_provider: string | null;
  repair_type: string;
  completion_date: string | null;
  repair_cost: number | null;
  conclusion: string | null;
  remark: string | null;
  created_at: string;
  created_by: string | null;
}

export interface Warranty {
  warranty_id: number;
  equipment_id: number;
  warranty_start: string;
  warranty_end: string;
  warranty_scope: string | null;
  provider_name: string | null;
  provider_contact: string | null;
  remark: string | null;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  attachment_id: number;
  equipment_id: number;
  file_name: string;
  file_size: number | null;
  file_type: string | null;
  tag: string | null;
  description: string | null;
  uploaded_at: string;
  uploaded_by: string | null;
}

export interface EquipmentAlert {
  equipment_id: number;
  equipment_code: string;
  name: string;
  alert_type: string;
  due_date: string;
  days_left: number;
  severity: string;
}

// 状态/枚举显示映射
export const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  in_use: { text: "在用", color: "green" },
  out_of_service: { text: "停用", color: "default" },
  scrapped: { text: "报废", color: "red" },
  in_repair: { text: "送修中", color: "orange" },
  in_calibration: { text: "校验中", color: "blue" },
};

export const CALIBRATION_RESULT_LABEL: Record<string, { text: string; color: string }> = {
  qualified: { text: "合格", color: "green" },
  unqualified: { text: "不合格", color: "red" },
  limited_use: { text: "限用", color: "orange" },
};

export const MAINTENANCE_TYPE_LABEL: Record<string, string> = {
  daily: "日常保养",
  periodic: "定期维护",
  special: "专项维护",
};

export const REPAIR_TYPE_LABEL: Record<string, string> = {
  internal: "内部维修",
  external: "外部维修",
};

export const ATTACHMENT_TAG_LABEL: Record<string, string> = {
  sop: "SOP",
  certificate: "证书",
  contract: "合同",
  photo: "照片",
  other: "其他",
};

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------
export const listEquipment = (params?: Record<string, unknown>) =>
  client.get<Equipment[]>("/api/equipment", { params });

export const getEquipment = (id: number) =>
  client.get<Equipment>(`/api/equipment/${id}`);

export const createEquipment = (data: EquipmentPayload) =>
  client.post<Equipment>("/api/equipment", data);

export const updateEquipment = (id: number, data: EquipmentPayload) =>
  client.patch<Equipment>(`/api/equipment/${id}`, data);

export const deactivateEquipment = (id: number, reason?: string) =>
  client.post<Equipment>(`/api/equipment/${id}/deactivate`, { reason });

export const listEquipmentCategories = () =>
  client.get<string[]>("/api/equipment/categories");

// ---- MDM 设备主数据(权威源) ----
export interface MdmEquipmentBrief {
  equipment_code: string;
  equipment_no?: string | null;
  fixed_asset_no?: string | null;
  equipment_name: string;
  category: string;
  model: string | null;
  manufacturer: string | null;
  serial_no: string | null;
  status: string;
}

// MDM 主数据状态(active/retired)显示映射
export const MDM_STATUS_LABEL: Record<string, { text: string; color: string }> = {
  active: { text: "在册", color: "green" },
  retired: { text: "已退役", color: "orange" },
};

export const searchMdmEquipments = (q: string, page = 1, pageSize = 20) =>
  client.get<{ data: MdmEquipmentBrief[] }>("/api/mdm/equipments", {
    params: { q, page, page_size: pageSize },
  });

export const createEquipmentFromMdm = (
  code: string,
  data: {
    location_room?: string | null;
    location_detail?: string | null;
    responsible_person?: string | null;
    commission_date?: string | null;
    status?: string;
    remark?: string | null;
  },
) => client.post<Equipment>(`/api/equipment/from-mdm/${encodeURIComponent(code)}`, data);

// 从 MDM 重新拉取主数据,整体覆盖身份字段快照(V1.4)
export const syncEquipmentFromMdm = (id: number) =>
  client.post<Equipment>(`/api/equipment/${id}/sync-mdm`);

// 从 MDM 批量引用建档(V1.4,台账初始化;运营字段留空待补)
export interface BatchFromMdmResult {
  created: number;
  skipped_existing: number;
  skipped_filtered: number;
  failed: string[];
}

export const batchCreateFromMdm = (params?: {
  categories?: string[] | null;
  include_retired?: boolean;
}) =>
  client.post<BatchFromMdmResult>("/api/equipment/batch-from-mdm", {
    categories: params?.categories ?? null,
    include_retired: params?.include_retired ?? false,
  }, { timeout: 300_000 });

export const equipmentAlerts = (days = 30) =>
  client.get<EquipmentAlert[]>("/api/equipment/alerts", { params: { days } });

export const listCalibrations = (id: number) =>
  client.get<Calibration[]>(`/api/equipment/${id}/calibrations`);

export const createCalibration = (id: number, data: Record<string, unknown>) =>
  client.post<Calibration>(`/api/equipment/${id}/calibrations`, data);

export const listMaintenances = (id: number) =>
  client.get<Maintenance[]>(`/api/equipment/${id}/maintenances`);

export const createMaintenance = (id: number, data: Record<string, unknown>) =>
  client.post<Maintenance>(`/api/equipment/${id}/maintenances`, data);

export const listRepairs = (id: number) =>
  client.get<Repair[]>(`/api/equipment/${id}/repairs`);

export const createRepair = (id: number, data: Record<string, unknown>) =>
  client.post<Repair>(`/api/equipment/${id}/repairs`, data);

export const completeRepair = (id: number, repairId: number, data: Record<string, unknown>) =>
  client.patch<Repair>(`/api/equipment/${id}/repairs/${repairId}`, data);

export const getWarranty = (id: number) =>
  client.get<Warranty | null>(`/api/equipment/${id}/warranty`);

export const upsertWarranty = (id: number, data: Record<string, unknown>) =>
  client.put<Warranty>(`/api/equipment/${id}/warranty`, data);

export const listAttachments = (id: number) =>
  client.get<Attachment[]>(`/api/equipment/${id}/attachments`);

export const uploadAttachment = (
  id: number,
  file: File,
  tag?: string,
  description?: string,
) => {
  const fd = new FormData();
  fd.append("file", file);
  if (tag) fd.append("tag", tag);
  if (description) fd.append("description", description);
  return client.post<Attachment>(`/api/equipment/${id}/attachments`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60_000,
  });
};

export const downloadAttachment = async (id: number, attachmentId: number, fileName: string) => {
  const resp = await client.get(`/api/equipment/${id}/attachments/${attachmentId}/download`, {
    responseType: "blob",
    timeout: 60_000,
  });
  const url = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
};

export const deleteAttachment = (id: number, attachmentId: number) =>
  client.delete(`/api/equipment/${id}/attachments/${attachmentId}`);
