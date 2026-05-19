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

export const listMaterials = (params?: Record<string, unknown>) =>
  client.get<Material[]>("/api/materials", { params });

export const getMaterial = (id: number) =>
  client.get<Material>(`/api/materials/${id}`);

export const createMaterial = (data: MaterialCreate) =>
  client.post<Material>("/api/materials", data);

export const updateMaterial = (id: number, data: Partial<MaterialCreate>) =>
  client.patch<Material>(`/api/materials/${id}`, data);

export const deactivateMaterial = (id: number, reason?: string) =>
  client.post<Material>(`/api/materials/${id}/deactivate`, { reason });

export const activateMaterial = (id: number) =>
  client.post<Material>(`/api/materials/${id}/activate`);

export const createFromMdm = (code: string) =>
  client.post<Material>(`/api/materials/from-mdm/${code}`);

export const mdmLookup = (code: string) =>
  client.get(`/api/mdm/materials/${code}`);

export const mdmSearch = (q: string, page = 1, pageSize = 20) =>
  client.get("/api/mdm/materials", { params: { q, page, page_size: pageSize } });

export const listCategories = () => client.get("/api/categories");

export const listCategoryValues = () =>
  client.get<string[]>("/api/categories/values");

export const listUnits = () => client.get("/api/units");
