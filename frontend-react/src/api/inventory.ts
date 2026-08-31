import client from "./client";

export interface BatchCreate {
  material_id: number;
  batch_no: string;
  expiry_date?: string | null;
  location_id: number;
  received_date: string;
  initial_qty: number;
  remark?: string | null;
  intake_type?: string | null;
  concentration?: string | null;
  extinction_coefficient?: number | null;
  serial_no?: string | null;
  asset_no?: string | null;
  responsible_person?: string | null;
  project_no?: string | null;
  originator_batch_no?: string | null;
  aliquot_date?: string | null;
  aliquot_spec?: string | null;
}

export interface Batch {
  batch_id: number;
  material_id: number;
  material_code: string | null;
  material_name: string | null;
  unit: string | null;
  batch_no: string;
  expiry_date: string | null;
  location_id: number;
  location_name: string | null;
  received_date: string;
  initial_qty: number;
  current_qty: number;
  remark: string | null;
  intake_type: string | null;
  concentration: string | null;
  extinction_coefficient: number | null;
  serial_no: string | null;
  asset_no: string | null;
  responsible_person: string | null;
  project_no: string | null;
  originator_batch_no: string | null;
  aliquot_date: string | null;
  aliquot_spec: string | null;
  created_at: string;
}

export interface TxnOutRequest {
  batch_id: number;
  qty: number;
  txn_date: string;
  purpose?: string | null;
  remark?: string | null;
}

export interface StockByMaterial {
  material_id: number;
  material_code: string;
  name_cn: string;
  category: string | null;
  material_type: string | null;
  manufacturer: string | null;
  spec_model: string | null;
  catalog_no: string | null;
  unit: string;
  is_active: boolean;
  safety_stock: number;
  total_qty: number;
  low_stock: boolean;
  aliquot_specs: string | null;  // 标准品:在库批次分装规格去重拼串
}

export interface StockByBatch {
  batch_id: number;
  material_id: number;
  material_code: string;
  name_cn: string;
  unit: string;
  batch_no: string;
  originator_batch_no: string | null;
  aliquot_spec: string | null;
  intake_operator_name: string | null;
  expiry_date: string | null;
  location_id: number;
  location_name: string;
  received_date: string;
  current_qty: number;
  days_to_expiry: number | null;
  is_active: boolean;
}

export interface Location {
  location_id: number;
  room_no: string;
  cabinet_no: string;
  layer_no: number;
  name: string;
  storage_condition: string | null;
}

export const createBatch = (data: BatchCreate) =>
  client.post<Batch>("/api/batches", data);

export const getBatch = (batchId: number) =>
  client.get<Batch>(`/api/batches/${batchId}`);

// 批次元信息可改字段(全部可选,只发改动的);reviewer_* 为第二位库管员的复核签名凭据。
export interface BatchMetaUpdate {
  expiry_date?: string | null;
  received_date?: string | null;
  remark?: string | null;
  concentration?: string | null;
  extinction_coefficient?: number | null;
  serial_no?: string | null;
  asset_no?: string | null;
  responsible_person?: string | null;
  project_no?: string | null;
  originator_batch_no?: string | null;
  aliquot_date?: string | null;
  aliquot_spec?: string | null;
  reviewer_username: string;
  reviewer_password: string;
}

export const updateBatchMeta = (batchId: number, data: BatchMetaUpdate) =>
  client.patch<Batch>(`/api/batches/${batchId}`, data);

export const outgoing = (data: TxnOutRequest) =>
  client.post("/api/inventory/out", data);

export const adjustStock = (data: { batch_id: number; qty: number; txn_date: string; remark?: string }) =>
  client.post("/api/inventory/adjust", data);

export const transferBatch = (data: {
  source_batch_id: number;
  dest_location_id: number;
  qty: number;
  txn_date: string;
  remark?: string;
}) => client.post("/api/inventory/transfer", data);

export const stockByMaterial = (params?: Record<string, unknown>) =>
  client.get<StockByMaterial[]>("/api/stock/by-material", { params });

export const stockByBatch = (params?: Record<string, unknown>) =>
  client.get<StockByBatch[]>("/api/stock/by-batch", { params });

export const expiryAlerts = (days?: number) =>
  client.get("/api/stock/alerts/expiry", { params: { days } });

export const lowStockAlerts = () =>
  client.get("/api/stock/alerts/low-stock");

export const listLocations = () => client.get<Location[]>("/api/locations");

// 批量入库(期3, 散放层多行)
export interface BulkIntakeRow {
  material_id: number;
  batch_no: string;
  expiry_date?: string | null;
  location_id: number;
  qty: number;
  concentration?: string | null;
  extinction_coefficient?: number | null;
  serial_no?: string | null;
  asset_no?: string | null;
  responsible_person?: string | null;
  project_no?: string | null;
  originator_batch_no?: string | null;
  aliquot_date?: string | null;
  aliquot_spec?: string | null;
  remark?: string | null;
}

export interface BulkIntakeRequest {
  received_date: string;
  intake_type?: string | null;
  rows: BulkIntakeRow[];
}

export interface BulkRowResult {
  index: number;
  status: "created" | "appended" | "error";
  batch_id: number | null;
  message: string | null;
}

export interface BulkIntakeResult {
  ok: boolean;
  created: number;
  appended: number;
  failed: number;
  results: BulkRowResult[];
}

export const bulkIntake = (data: BulkIntakeRequest) =>
  client.post<BulkIntakeResult>("/api/intake/bulk", data);
