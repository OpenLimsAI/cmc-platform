import type { DataSource } from '@/types'
export interface SimilarityRequest {
  project_id: string; data_source: DataSource; sample_type: string | null
  test_types: string[]; placement_statuses: string[]; batch_numbers: string[]; attribute_names: string[]
  reference_lines: string[]; comparison_lines: string[]; reference_sd_multiplier: number
  tier1_attribute_names: string[]; confidence_level: 0.9 | 0.95; bf_threshold: number
  tier2_hit_ratio: number; delta_mode: 'auto' | 'manual'; manual_delta: number | null
}
export interface SimilarityGroup {
  line: string; n: number; mean: number | null; sd: number | null; min: number | null; max: number | null; excluded_n: number
  mean_ci_lower: number | null; mean_ci_upper: number | null
  points: {batch_number: string | null; value: number; source_result_id: string | null; group_id: string | null}[]
}
export interface SimilarityComparison extends SimilarityGroup {
  mean_difference: number | null; differences: (number | null)[]; band_hits: number | null; band_ratio: number | null
  exploratory_statistics: Record<string, string | number | null>
}
export interface SimilarityPanel {
  panel_id: string; scope: Record<string,string | null>; reference: SimilarityGroup; comparisons: SimilarityComparison[]
  band: {lower: number | null; upper: number | null; half_width: number | null; basis: 'manual_delta' | 'reference_sd'; k: number}; warnings: string[]; judgement: string
}
