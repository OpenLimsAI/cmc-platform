import type { DataSource, ReleaseRequest } from '@/types'

export const RELEASE_STORAGE_KEY = 'qap.release.filter'
export const emptyDraft = (projectId = '', dataSource: DataSource = 'RD'): ReleaseRequest => ({
  project_id: projectId, sample_type: null, production_line_ids: [], group_ids: [],
  batch_numbers: [], test_types: [], placement_statuses: [], batch_years: [], include_unknown_batch_year: false,
  attribute_names: [], capability_mode: 'population', data_source: dataSource,
})

/** 只恢复合法筛选字段；损坏的浏览器缓存不能使页面崩溃。 */
export function parseReleaseDraft(raw: string | null): ReleaseRequest {
  const draft = emptyDraft()
  try {
    const value = JSON.parse(raw || '{}')
    if (!value || typeof value !== 'object') return draft
    if (value.data_source !== undefined && value.data_source !== 'RD' && value.data_source !== 'QC' && value.data_source !== 'EXCEL') return draft
    if (value.data_source === 'QC' || value.data_source === 'EXCEL') draft.data_source = value.data_source
    if (value.sd_reference_mode === 'current' || value.sd_reference_mode === 'history') draft.sd_reference_mode = value.sd_reference_mode
    if (Number.isInteger(value.lookback_years) && value.lookback_years >= 1 && value.lookback_years <= 10) draft.lookback_years = value.lookback_years
    if (typeof value.project_id === 'string') draft.project_id = value.project_id
    if (typeof value.sample_type === 'string') draft.sample_type = value.sample_type
    for (const field of ['production_line_ids', 'group_ids', 'batch_numbers', 'test_types', 'placement_statuses', 'attribute_names'] as const) {
      if (Array.isArray(value[field]) && value[field].every((item: unknown) => typeof item === 'string')) draft[field] = value[field]
    }
    if (Array.isArray(value.batch_years) && value.batch_years.every(Number.isInteger)) draft.batch_years = value.batch_years
    draft.include_unknown_batch_year = value.include_unknown_batch_year === true
    if (value.capability_mode === 'sample') draft.capability_mode = 'sample'
  } catch { /* 使用安全空选择 */ }
  return draft
}

export function readReleaseDraft(): ReleaseRequest {
  try { return parseReleaseDraft(localStorage.getItem(RELEASE_STORAGE_KEY)) } catch { return emptyDraft() }
}

export function saveReleaseDraft(draft: ReleaseRequest) {
  try { localStorage.setItem(RELEASE_STORAGE_KEY, JSON.stringify(draft)) } catch { /* 仍能正常分析 */ }
}
