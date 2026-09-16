export interface PreviewTemplate {
  template_code: string
  version: string
  label: string
  sheet_name: string
  headers: string[]
  max_file_bytes: number
  header_row?: number
  label_row?: number | null
  data_start_row?: number
}

export interface ImportCapabilities {
  can_commit: false
  templates: PreviewTemplate[]
  business_validation: 'pending'
}

export interface PreviewCell {
  coordinate: string
  field_name: string | null
  source_header: string | null
  value: unknown
  data_type: string
  number_format: string
  cached_value: unknown
}

export interface PreviewRow {
  row_number: number
  cells: PreviewCell[]
}

export interface PreviewIssue {
  code: string
  message: string
  severity: string
  sheet_name: string | null
  row_number: number | null
  column_name: string | null
  coordinate: string | null
}

export interface StructurePreview {
  columns?: { column_index: number; source_header: string | null; source_label: string | null; field_name: string | null }[]
  original_filename: string
  file_sha256: string
  byte_size: number
  template_code: string
  template_version: string
  sheet_name: string
  rows: PreviewRow[]
  issues: PreviewIssue[]
  blank_row_count: number
  parser_version: string
  business_validation: 'pending'
  can_commit: false
  structure_valid: boolean
}

export interface PreviewResponse {
  preview: StructurePreview
  actor: { username: string; full_name: string | null }
  preview_only: true
  total_row_count: number
  total_issue_count: number
  rows_truncated: boolean
  issues_truncated: boolean
}
