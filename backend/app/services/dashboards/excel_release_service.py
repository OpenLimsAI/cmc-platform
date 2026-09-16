"""Excel 放行原值描述统计和明确的年份参考；旧规格只列出，不自动生效。"""
import numpy as np
import pandas as pd
from app.schemas.release import ReleaseRequest
from app.services.dashboards.release_filters import filter_release_rows
from app.services.dashboards.release_service import analyze_qc_release, _f
from app.services.mapping.batch import extract_year_from_batch
from app.services.specs import DEFAULT_SPEC_LIMITS, PROJECT_SPEC_LIMITS, normalize_sample_type


def legacy_spec_candidate(project, attribute, sample):
    section = normalize_sample_type(sample)
    rules = PROJECT_SPEC_LIMITS.get(project, {})
    if section in rules and attribute in rules[section]:
        bounds, origin = rules[section][attribute], f'{project}/{section}'
    elif attribute in rules.get('COMMON', {}):
        bounds, origin = rules['COMMON'][attribute], f'{project}/COMMON'
    elif attribute in DEFAULT_SPEC_LIMITS:
        bounds, origin = DEFAULT_SPEC_LIMITS[attribute], 'DEFAULT（非项目专属）'
    else:
        bounds, origin = (None, None), None
    return {'lsl_raw': bounds[0], 'usl_raw': bounds[1], 'origin': origin,
            'status': 'unverified_legacy_reference', 'unit': None,
            'source': '旧看板 components/spec_limits.py 的移植配置', 'effective_version': None}


def analyze_excel_release(df: pd.DataFrame, req: ReleaseRequest) -> tuple[list[dict], int]:
    baseline = filter_release_rows(df, req.model_copy(update={'batch_years': None, 'include_unknown_batch_year': False}))
    selected = filter_release_rows(baseline, req)
    panels = analyze_qc_release(selected, project_id=req.project_id, sample_type=req.sample_type,
                                capability_mode=req.capability_mode, raw_statistics=True)
    for panel in panels:
        scope = panel['scope']
        reference = baseline
        for field, value in scope.items():
            column = reference[field]
            reference = reference[column.isna() if value is None else column.map(lambda x: None if pd.isna(x) else str(x)).eq(value)]
        years = reference.batch_number.map(extract_year_from_batch)
        if req.sd_reference_mode == 'history':
            selected_years = req.batch_years or selected.batch_number.map(extract_year_from_batch).dropna().tolist()
            anchor = max(selected_years) if selected_years else None
            reference_years = list(range(int(anchor) - req.lookback_years, int(anchor))) if anchor is not None else []
            reference = reference[years.isin(reference_years)]
        else:
            reference = filter_release_rows(reference, req)
            reference_years = sorted({int(y) for y in reference.batch_number.map(extract_year_from_batch).dropna()})
        values = pd.to_numeric(reference.value, errors='coerce')
        values = values[np.isfinite(values)].to_numpy(dtype=float)
        n = len(values)
        mean = _f(np.mean(values)) if n else None
        sd = _f(np.std(values, ddof=1)) if n > 1 else None
        panel['reference_summary'] = {
            'mode': req.sd_reference_mode, 'years': reference_years, 'n': n, 'mean': mean, 'sd_sample': sd,
            'min': _f(np.min(values)) if n else None, 'max': _f(np.max(values)) if n else None,
            'rsd_pct': _f(sd / mean * 100) if sd is not None and mean else None,
            'sd_available': n >= 3 and sd is not None,
        }
        panel['sd_lines'] = {'mean': mean, **{key: _f(mean + factor * sd) if n >= 3 and mean is not None and sd is not None else None
            for key, factor in [('plus_1_5sd',1.5),('minus_1_5sd',-1.5),('plus_3sd',3),('minus_3sd',-3)]}}
        panel['statistics_basis'] = 'stored_raw_values_no_unit_conversion'
        panel['legacy_spec_candidate'] = legacy_spec_candidate(req.project_id, panel['attribute_name'], scope.get('sample_type'))
    return panels, len(selected)
