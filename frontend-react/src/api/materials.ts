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

// 物料主数据为只读"物料查询"(V1.3):新增/编辑/停用统一在 MDM Portal,
// 此处不提供本地 CRUD 调用(后端兜底端点仍在,仅 API 直调)
export const listMaterials = (params?: Record<string, unknown>) =>
  client.get<Material[]>("/api/materials", { params });

export const createFromMdm = (code: string) =>
  client.post<Material>(`/api/materials/from-mdm/${code}`);

export const mdmLookup = (code: string) =>
  client.get(`/api/mdm/materials/${code}`);

export const listCategoryValues = () =>
  client.get<string[]>("/api/categories/values");
