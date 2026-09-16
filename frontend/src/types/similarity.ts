import type { DataSource } from '@/types'
export interface SimilarityRequest {
  project_id: string; data_source: DataSource; sample_type: string | null
  test_types: string[]; placement_statuses: string[]; batch_numbers: string[]; attribute_names: string[]
  reference_lines: string[]; comparison_lines: string[]; reference_sd_multiplier: number
}
export interface SimilarityGroup {
  line: string; n: number; mean: number | null; sd: number | null; min: number | null; max: number | null; excluded_n: number
  points: {batch_number: string | null; value: number; source_result_id: string | null; group_id: string | null}[]
}
export interface SimilarityComparison extends SimilarityGroup {
  mean_difference: number | null; differences: (number | null)[]; band_hits: number | null; band_ratio: number | null
}
export interface SimilarityPanel {
  panel_id: string; scope: Record<string,string | null>; reference: SimilarityGroup; comparisons: SimilarityComparison[]
  band: {lower: number | null; upper: number | null; k: number}; warnings: string[]; judgement: string
}
