import client from "./client";

export interface Material {
  material_id: number;
  material_code: string;
  name_cn: string;
  category: string | null;
  material_type: string | null;
  grade: string | null;
  manufacturer: string | null;
  spec_model: string | null;
  catalog_no: string | null;
  unit: string;
  package_spec: string | null;
  hazard_class: string[] | null;
  remark: string | null;
  safety_stock: number;
  data_source: string | null;
  is_active: boolean;
  deactivated_at: string | null;
  deactivated_by: string | null;
  deactivate_reason: string | null;
  import_batch_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialCreate {
  material_code: string;
  name_cn: string;
  unit: string;
  category?: string | null;
  material_type?: string | null;
  grade?: string | null;
  manufacturer?: string | null;
  spec_model?: string | null;
  catalog_no?: string | null;
  package_spec?: string | null;
  hazard_class?: string[] | null;
  remark?: string | null;
  safety_stock?: number;
}

// 保留编码:部门内无 MDM 编码的临时/本地物料(允许多条共存, 按 material_id 区分)
export const TT_INTERNAL_CODE = "TT内部物料";

export interface Unit {
  unit: string;
  description: string | null;
}

// 物料主数据为只读"物料查询"(V1.3):MDM 物料的新增/编辑/停用统一在 MDM Portal。
// 例外:无编码本地物料(分装原研药等)在入库页就地登记, 走 createMaterial。
export const listMaterials = (params?: Record<string, unknown>) =>
  client.get<Material[]>("/api/materials", { params });

export const listUnits = () => client.get<Unit[]>("/api/units");

// 就地登记本地物料(无 MDM 编码), material_code 传 TT_INTERNAL_CODE
export const createMaterial = (data: MaterialCreate) =>
  client.post<Material>("/api/materials", data);

export const createFromMdm = (code: string) =>
  client.post<Material>(`/api/materials/from-mdm/${code}`);

export const mdmLookup = (code: string) =>
  client.get(`/api/mdm/materials/${code}`);

export const listCategoryValues = () =>
  client.get<string[]>("/api/categories/values");
