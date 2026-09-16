// 与后端 Pydantic/服务返回结构对应的 TS 类型
export type DataSource = 'RD' | 'QC' | 'EXCEL'

export interface ProjectMeta {
  project_id: string
  n: number
}

export interface AttributeMeta {
  attribute_name: string
  attribute_raws: string[]
  n: number
}

export interface Coverage {
  total_rows: number
  data_type_counts: Record<string, number>
  attribute_mapped_rows: number
  attribute_unmapped_rows: number
  attribute_mapped_pct: number
  distinct_attribute_raw: number
  distinct_attribute_unmapped: number
}

export interface ReleasePoint {
  batch_number: string | null
  lot_sort_key: number
  year: number | null
  group_id: string | null
  value: number | null
}

export interface ReleaseGroup {
  group_id: string | null
  n: number
  mean: number | null
  sd: number | null
}

export interface ReleaseAttribute {
  statistics_basis?: string
  reference_summary?: { mode: string; years: number[]; n: number; mean: number | null; sd_sample: number | null; min: number | null; max: number | null; rsd_pct: number | null; sd_available: boolean }
  legacy_spec_candidate?: { lsl_raw: number | null; usl_raw: number | null; origin: string | null; status: string; source: string }
  panel_id?: string
  scope?: Record<string, string | null>
  statistics_available?: boolean
  observations_only?: boolean
  attribute_name: string
  units: string[]
  is_pct: boolean
  n: number
  mean: number | null
  sd_sample: number | null
  sd_population: number | null
  min: number | null
  max: number | null
  rsd_pct: number | null
  spec: { lsl: number | null; usl: number | null }
  capability: { value: number | null; label: string | null; mode: string }
  sd_lines: {
    mean: number | null
    plus_1_5sd: number | null
    minus_1_5sd: number | null
    plus_3sd: number | null
    minus_3sd: number | null
  }
  groups: ReleaseGroup[]
  points: ReleasePoint[]
}

export interface ReleaseRequest {
  project_id: string
  sample_type?: string | null
  production_line_ids?: string[] | null
  group_ids?: string[] | null
  batch_numbers?: string[] | null
  test_types?: string[] | null
  batch_years?: number[] | null
  include_unknown_batch_year?: boolean
  attribute_names?: string[] | null
  capability_mode?: 'population' | 'sample'
  sd_reference_mode?: 'current' | 'history'
  lookback_years?: number
  placement_statuses?: string[]
  data_source: DataSource
}

export interface ReleaseOptions {
  placement_statuses?: string[]
  production_line_ids: string[]
  group_ids: string[]
  batch_numbers: string[]
  test_types: string[]
  sample_types: string[]
  attributes: AttributeMeta[]
  batch_years: number[]
  unknown_batch_year_count: number
  row_count: number
  year_basis: 'legacy_batch_number_inference'
}
