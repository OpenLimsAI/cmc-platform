import type { AttributeMeta } from '@/types'

export interface StabilityRequest {
  project_id: string
  sample_types: string[]
  test_types: string[]
  production_line_ids: string[]
  group_ids: string[]
  batch_numbers: string[]
  attribute_names: string[]
  placement_statuses?: string[]
  data_source: 'RD' | 'QC' | 'EXCEL'
}
export interface StabilityOptions {
  placement_statuses?: string[]
  sample_types: string[]; test_types: string[]; production_line_ids: string[]; group_ids: string[]; batch_numbers: string[]
  attributes: AttributeMeta[]; row_count: number; project_row_count: number
}
export interface StabilityObservation {
  observation_id: string; batch_number: string | null; production_line_id: string | null; group_id: string | null
  source_system: string | null; sample_id: string | null; source_test_id: string | null; source_result_id: string | null
  value_str: string | null; received_dt: string | null
  timepoint: number | null; timepoint_raw: string | null; value: number | null; value_raw: string | null
  issues: string[]; plottable: boolean
}
export type StabilityFit = { available: false; reason: string } | {
  available: true; n: number; slope: number; intercept: number; r_squared: number | null; x: number[]; y: number[]
}
export interface StabilitySeries {
  series_id: string; production_line_id: string | null; group_id: string | null; fit: StabilityFit
}
export interface StabilityBatch extends StabilitySeries { batch_number: string | null; connect_points: boolean; points: StabilityObservation[] }
export interface StabilityGroup extends StabilitySeries { points: { timepoint: number; n: number; mean: number | null; sd: number | null; min?: number; max?: number }[] }
export interface StabilityPanel {
  panel_id: string; attribute_name: string; attribute_raw: string | null; sample_type: string | null; test_type: string | null
  placement_status?: string | null; sub_lot?: string | null
  method_code: string | null; unit: string | null; timepoint_unit: string | null
  n: number; plotted_n: number; timepoint_count: number; statistics_available: boolean; warnings: string[]
  observations: StabilityObservation[]; batches: StabilityBatch[]; groups: StabilityGroup[]
}
