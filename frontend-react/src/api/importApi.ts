import client from "./client";

export interface ImportPreviewRow {
  row_index: number;
  material_code: string | null;
  name_cn: string | null;
  action: "INSERT" | "UPDATE" | "ERROR";
  errors: string[];
  warnings: string[];
  raw: Record<string, unknown>;
}

export interface ImportPreviewResult {
  total_rows: number;
  insert_count: number;
  update_count: number;
  error_count: number;
  leading_zero_codes: string[];
  new_categories: string[];
  new_units: string[];
  rows: ImportPreviewRow[];
}

export interface ImportCommitResult {
  import_id: number;
  total_rows: number;
  inserted_rows: number;
  updated_rows: number;
  failed_rows: number;
}

export interface ImportLogItem {
  import_id: number;
  file_name: string | null;
  imported_at: string;
  operator: string | null;
  total_rows: number;
  inserted_rows: number;
  updated_rows: number;
  failed_rows: number;
  error_detail: unknown;
}

export const dryRunImport = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return client.post<ImportPreviewResult>("/api/import/materials/dry-run", fd, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60_000,
  });
};

export const commitImport = (data: {
  file_name: string;
  auto_create_units: boolean;
  rows: Record<string, unknown>[];
}) =>
  client.post<ImportCommitResult>("/api/import/materials/commit", data, {
    timeout: 60_000,
  });

export const listImportLogs = (limit = 20) =>
  client.get<ImportLogItem[]>("/api/import/logs", { params: { limit } });
