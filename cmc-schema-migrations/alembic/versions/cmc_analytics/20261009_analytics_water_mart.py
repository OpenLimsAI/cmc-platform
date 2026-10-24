# -*- coding: utf-8 -*-
"""Current reviewed water mart contract; no stored history or source writes.

Business contract: cmc-water-system-dashboard/docs/11-water-mart-design.md.
This revision requires the v2 staging producer; no new method selection.
"""
from alembic import op

revision = 'analytics_water_mart_20261009'
down_revision = 'analytics_water_final_20261009'
branch_labels = None
depends_on = None

VIEW_DEFINITIONS = (
    ('v_water_result', r"""WITH selected AS (
    SELECT w.*,
      NULLIF(btrim(unit), '') AS source_unit_clean,
      regexp_match(btrim(displayvalue, E' \t\n\r\f'),
        '^([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?)$') AS numeric_match,
      regexp_match(btrim(displayvalue, E' \t\n\r\f'),
        '^(<=|>=|<|>|≤|≥|＜|＞)[[:space:]]*([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?)$') AS censored_match,
      CASE
        WHEN (paramlistid = '电导率' AND paramlistversionid IN ('1','2') AND paramid IN ('结果','报告值'))
          OR (paramlistid IN ('电导率-方法1','电导率-<通则0681>注射用水测定法（第一步）')
              AND paramlistversionid = '1' AND paramid = '结果') THEN 'conductivity'
        WHEN (paramlistid = '总有机碳' AND paramlistversionid = '1' AND paramid = 'TOC报告值')
          OR (paramlistid = '总有机碳' AND paramlistversionid = '2' AND paramid = '结果') THEN 'toc'
        WHEN paramlistid = 'pH值' AND paramlistversionid = '1' AND paramid = '结果' THEN 'ph'
      END AS approved_unit_scope
    FROM staging.stg_lv_test_result_wide w
    WHERE source_system = 'gmp_labvantage' AND sdcid = 'Sample'
      AND samplesubtypeid IN ('注射用水','纯化水','纯蒸汽') AND samplestatus = 'Reviewed'
      AND selection_rule IN ('water_system_v2','water_conductivity_method1_numeric_v2')
), interpreted AS (
    SELECT s.*,
      CASE approved_unit_scope
        WHEN 'conductivity' THEN CASE WHEN source_unit_clean IS NULL OR source_unit_clean IN ('μS/cm','µS/cm','uS/cm') THEN 'μS/cm' END
        WHEN 'toc' THEN CASE WHEN source_unit_clean IS NULL OR lower(source_unit_clean) = 'ppb' THEN 'ppb' END
        WHEN 'ph' THEN NULL
        ELSE source_unit_clean
      END AS analysis_unit,
      CASE
        WHEN approved_unit_scope = 'ph' THEN CASE WHEN source_unit_clean IS NULL THEN 'dimensionless' ELSE 'conflict' END
        WHEN approved_unit_scope = 'conductivity' AND source_unit_clean IS NOT NULL AND source_unit_clean NOT IN ('μS/cm','µS/cm','uS/cm') THEN 'conflict'
        WHEN approved_unit_scope = 'toc' AND source_unit_clean IS NOT NULL AND lower(source_unit_clean) <> 'ppb' THEN 'conflict'
        WHEN approved_unit_scope IN ('conductivity','toc') THEN CASE WHEN source_unit_clean IS NULL THEN 'business_confirmed' ELSE 'normalized' END
        WHEN source_unit_clean IS NULL THEN 'missing'
        ELSE 'source'
      END AS unit_status,
      CASE approved_unit_scope
        WHEN 'conductivity' THEN 'water_conductivity_unit_us_cm_v1'
        WHEN 'toc' THEN 'water_toc_unit_ppb_v1'
        WHEN 'ph' THEN 'water_ph_dimensionless_v1'
        ELSE 'water_source_unit_v1'
      END AS unit_rule_version,
      COALESCE(CASE result_kind
        WHEN 'exact_numeric' THEN numeric_match IS NOT NULL
          AND plot_value = (numeric_match)[1]::numeric
          AND result_operator IS NULL AND result_bound IS NULL
          AND plot_value_rule = 'water_exact_numeric_v1'
        WHEN 'censored' THEN censored_match IS NOT NULL
          AND result_operator = CASE (censored_match)[1] WHEN '＜' THEN '<' WHEN '＞' THEN '>' WHEN '≤' THEN '<=' WHEN '≥' THEN '>=' ELSE (censored_match)[1] END
          AND result_bound = (censored_match)[2]::numeric
          AND CASE WHEN paramlistid = '微生物限度' AND paramid = '报告值'
                     AND result_operator = '<' AND result_bound = 1
                   THEN plot_value = 0 AND plot_value_rule = 'water_microbiology_lt1_zero_v1'
                   ELSE plot_value = result_bound AND plot_value_rule = 'water_censored_bound_plot_v1' END
        ELSE false END, false) AS plot_metadata_valid,
      jsonb_build_object('source_system',source_system,'sdcid',sdcid,'keyid1',keyid1,'keyid2',keyid2,'keyid3',keyid3,
        'paramlistid',paramlistid,'paramlistversionid',paramlistversionid,'variantid',variantid,'dataset',dataset,
        'paramid',paramid,'paramtype',paramtype,'replicateid',replicateid) AS source_key
    FROM selected s
), qualified AS (
    SELECT i.*,
      CASE WHEN unit_status = 'dimensionless' THEN '无量纲'
           WHEN unit_status = 'conflict' THEN source_unit_clean ELSE analysis_unit END AS display_unit,
      CASE WHEN result_kind = 'exact_numeric' AND plot_metadata_valid THEN plot_value END AS exact_numeric_value,
      CASE
        WHEN s_sampleid IS NULL OR s_sampleid IS DISTINCT FROM keyid1 THEN 'invalid_sample_identity'
        WHEN result_role IS DISTINCT FROM 'reported_result' OR result_kind IS NULL OR result_kind NOT IN ('exact_numeric','censored') THEN 'non_numeric_result'
        WHEN NOT plot_metadata_valid THEN 'invalid_plot_metadata'
        WHEN NULLIF(btrim(samplepointid),'') IS NULL OR NULLIF(btrim(samplepoint_code),'') IS NULL THEN 'missing_samplepoint'
        WHEN trend_dt IS NULL THEN 'missing_trend_date'
        WHEN unit_status = 'conflict' THEN 'unit_conflict'
        WHEN unit_status = 'missing' THEN 'missing_unit'
      END AS not_plotted_reason
    FROM interpreted i
)
SELECT q.*,
  s_sampleid AS sample_id, samplesubtypeid AS water_type, samplestatus AS sample_status,
  samplepointid AS samplepoint_id, displayvalue AS display_value, unit AS source_unit,
  trend_dt AS trend_at, trend_dt_source AS trend_date_source, _etl_loaded_at AS staging_loaded_at,
  not_plotted_reason IS NULL AS plot_eligible,
  jsonb_build_array(samplesubtypeid,samplepointid,workitemid,paramlistid,paramlistversionid,variantid,paramid,paramtype,analysis_unit)
    || CASE WHEN unit_status IN ('missing','conflict') OR NULLIF(btrim(samplepointid),'') IS NULL
            THEN jsonb_build_array(source_key) ELSE '[]'::jsonb END AS comparison_key,
  'water_mart_v1'::text AS mart_rule_version
FROM qualified q"""),
    ('v_water_numeric_trend', r"""SELECT * FROM mart.v_water_result WHERE plot_eligible"""),
    ('v_water_sample', r"""WITH attributes AS (
    SELECT DISTINCT source_system, sample_id, water_type, sample_status, sample_name, samplepoint_id, samplepoint_code, samplepoint_name, samplepoint_mapping_source, samplepoint_mapping_scope, samplepoint_source_moddt, samplepoint_extracted_at, trend_at, trend_date_source, collectiondt, sample_eventdt, receiveddt, sample_createdt FROM mart.v_water_result
), consistent AS (
    SELECT source_system, sample_id FROM attributes
    GROUP BY source_system, sample_id HAVING count(*) = 1
), counts AS (
    SELECT source_system, sample_id, count(*) AS result_count,
      count(*) FILTER (WHERE plot_eligible) AS trend_result_count,
      count(*) FILTER (WHERE result_role = 'conclusion') AS conclusion_count,
      count(DISTINCT jsonb_build_array(sdcid,keyid1,keyid2,keyid3,paramlistid,paramlistversionid,variantid,dataset)) AS dataset_count,
      max(staging_loaded_at) AS staging_loaded_at
    FROM mart.v_water_result GROUP BY source_system, sample_id
)
SELECT a.*, c.result_count,c.trend_result_count,c.conclusion_count,c.dataset_count,c.staging_loaded_at,
  'water_mart_v1'::text AS mart_rule_version
FROM attributes a JOIN consistent k USING (source_system,sample_id) JOIN counts c USING (source_system,sample_id)"""),
    ('v_water_review_item', r"""WITH result_issues AS (
    SELECT 'result'::text AS entity_grain, e.issue_type, r.source_system,r.sample_id,r.water_type,r.sample_status,
      r.workitemid,r.paramlistid,r.paramlistversionid,r.source_key,
      r.display_value,r.source_unit,r.unit_status,r.trend_at,
      jsonb_build_object('not_plotted_reason',r.not_plotted_reason,'unit_rule_version',r.unit_rule_version) AS details
    FROM mart.v_water_result r
    CROSS JOIN LATERAL (VALUES
      ('unparsed_result', r.result_kind = 'unparsed'),
      ('missing_result', r.result_kind = 'missing' OR r.result_kind IS NULL),
      ('invalid_sample_identity', r.sample_id IS NULL OR r.sample_id IS DISTINCT FROM r.keyid1),
      ('invalid_plot_metadata', r.result_kind IN ('exact_numeric','censored') AND NOT r.plot_metadata_valid),
      ('missing_unit', r.result_kind IN ('exact_numeric','censored') AND r.unit_status = 'missing'),
      ('unit_conflict', r.unit_status = 'conflict'),
      ('missing_samplepoint', NULLIF(btrim(r.samplepoint_id),'') IS NULL OR NULLIF(btrim(r.samplepoint_code),'') IS NULL),
      ('missing_trend_date', r.trend_at IS NULL)
    ) e(issue_type, applies) WHERE e.applies
), attribute_issues AS (
    SELECT 'sample'::text AS entity_grain,'sample_attributes_conflict'::text AS issue_type,
      source_system,sample_id,NULL::text AS water_type,NULL::text AS sample_status,
      NULL::text AS workitemid,NULL::text AS paramlistid,NULL::text AS paramlistversionid,
      jsonb_build_object('source_system',source_system,'sample_id',sample_id) AS source_key,
      NULL::text AS display_value,NULL::text AS source_unit,NULL::text AS unit_status,NULL::timestamptz AS trend_at,
      jsonb_build_object('attribute_versions',count(DISTINCT jsonb_build_array(water_type,sample_status,sample_name,samplepoint_id,samplepoint_code,samplepoint_name,samplepoint_mapping_source,samplepoint_mapping_scope,samplepoint_source_moddt,samplepoint_extracted_at,trend_at,trend_date_source,collectiondt,sample_eventdt,receiveddt,sample_createdt))) AS details
    FROM mart.v_water_result GROUP BY source_system,sample_id
    HAVING count(DISTINCT jsonb_build_array(water_type,sample_status,sample_name,samplepoint_id,samplepoint_code,samplepoint_name,samplepoint_mapping_source,samplepoint_mapping_scope,samplepoint_source_moddt,samplepoint_extracted_at,trend_at,trend_date_source,collectiondt,sample_eventdt,receiveddt,sample_createdt)) > 1
), unsupported_rules AS (
    SELECT 'result'::text AS entity_grain,'unsupported_selection_rule'::text AS issue_type,
      w.source_system,w.s_sampleid AS sample_id,w.samplesubtypeid AS water_type,w.samplestatus AS sample_status,
      w.workitemid,w.paramlistid,w.paramlistversionid,
      jsonb_build_object('source_system',w.source_system,'sdcid',w.sdcid,'keyid1',w.keyid1,'keyid2',w.keyid2,'keyid3',w.keyid3,
        'paramlistid',w.paramlistid,'paramlistversionid',w.paramlistversionid,'variantid',w.variantid,'dataset',w.dataset,
        'paramid',w.paramid,'paramtype',w.paramtype,'replicateid',w.replicateid) AS source_key,
      w.displayvalue AS display_value,w.unit AS source_unit,NULL::text AS unit_status,w.trend_dt AS trend_at,
      jsonb_build_object('selection_rule',w.selection_rule) AS details
    FROM staging.stg_lv_test_result_wide w
    WHERE w.source_system = 'gmp_labvantage' AND w.sdcid = 'Sample'
      AND w.samplesubtypeid IN ('注射用水','纯化水','纯蒸汽') AND w.samplestatus = 'Reviewed'
      AND (w.selection_rule IS NULL OR w.selection_rule NOT IN ('water_system_v2','water_conductivity_method1_numeric_v2'))
), method_headers AS (
    SELECT DISTINCT d.source_system,d.sdcid,d.keyid1,d.keyid2,d.keyid3,d.workitemid,d.paramlistid,d.paramlistversionid,
      s.samplesubtypeid,s.samplestatus
    FROM staging.stg_lv_dataset d JOIN staging.stg_lv_sample s
      ON s.source_system=d.source_system AND s.s_sampleid=d.keyid1
    WHERE d.source_system='gmp_labvantage' AND d.sdcid='Sample'
      AND s.samplesubtypeid IN ('注射用水','纯化水','纯蒸汽') AND s.samplestatus='Reviewed'
), method_issues AS (
    SELECT 'sample_method'::text AS entity_grain,'no_selected_final_result'::text AS issue_type,
      h.source_system,h.keyid1 AS sample_id,h.samplesubtypeid AS water_type,h.samplestatus AS sample_status,
      h.workitemid,h.paramlistid,h.paramlistversionid,
      jsonb_build_object('source_system',h.source_system,'sdcid',h.sdcid,'keyid1',h.keyid1,'keyid2',h.keyid2,'keyid3',h.keyid3,
        'workitemid',h.workitemid,'paramlistid',h.paramlistid,'paramlistversionid',h.paramlistversionid) AS source_key,
      NULL::text AS display_value,NULL::text AS source_unit,NULL::text AS unit_status,NULL::timestamptz AS trend_at,
      jsonb_build_object('meaning','Header exists without a selected final result; not a missed-test determination') AS details
    FROM method_headers h WHERE NOT EXISTS (
      SELECT 1 FROM mart.v_water_result r WHERE r.source_system=h.source_system AND r.sdcid=h.sdcid
        AND r.keyid1=h.keyid1 AND r.keyid2=h.keyid2 AND r.keyid3=h.keyid3
        AND r.workitemid IS NOT DISTINCT FROM h.workitemid
        AND r.paramlistid=h.paramlistid AND r.paramlistversionid=h.paramlistversionid)
)
SELECT x.*, 'water_mart_v1'::text AS mart_rule_version
FROM (SELECT * FROM result_issues UNION ALL SELECT * FROM attribute_issues
      UNION ALL SELECT * FROM unsupported_rules UNION ALL SELECT * FROM method_issues) x"""),
)

def upgrade():
    bind = op.get_bind()
    if bind.exec_driver_sql('SELECT current_database()').scalar() not in ('cmc_analytics', 'cmc_analytics_training'):
        raise RuntimeError('Unexpected water mart migration database')
    bind.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    # Never overwrite an independently created object under the same name.
    for name, _ in VIEW_DEFINITIONS:
        if bind.exec_driver_sql(f"SELECT to_regclass('mart.{name}')").scalar() is not None:
            raise RuntimeError(f'Water mart object already exists: {name}')
    for name, query in VIEW_DEFINITIONS:
        bind.exec_driver_sql(f'CREATE VIEW mart.{name} WITH (security_barrier=true) AS ' + query)
        bind.exec_driver_sql(f"COMMENT ON VIEW mart.{name} IS 'water_mart_v1: current Reviewed final results; ordinary view, no historical snapshot; plot zero is not an exact measurement'")
        bind.exec_driver_sql(f'REVOKE ALL ON mart.{name} FROM PUBLIC')
        for role in ('lims_reader', 'analytics_reader'):
            if bind.exec_driver_sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{role}'").scalar():
                bind.exec_driver_sql(f'GRANT USAGE ON SCHEMA mart TO {role}')
                bind.exec_driver_sql(f'REVOKE ALL ON mart.{name} FROM {role}')
                bind.exec_driver_sql(f'GRANT SELECT ON mart.{name} TO {role}')
    bind.exec_driver_sql("COMMENT ON COLUMN mart.v_water_result.exact_numeric_value IS 'Exact parsed report number only; NULL for censored and qualitative results'")
    bind.exec_driver_sql("COMMENT ON COLUMN mart.v_water_result.source_unit IS 'Unmodified staging source unit; analysis_unit and display_unit are derived under versioned rules'")
    bind.exec_driver_sql("COMMENT ON COLUMN mart.v_water_result.plot_value IS 'Plot coordinate only; microbiology <1 plots at 0, never interpreted as an exact measured zero'")


def downgrade():
    # Explicit reviewed rollback only. RESTRICT protects other database consumers.
    for name, _ in reversed(VIEW_DEFINITIONS):
        op.execute(f'DROP VIEW mart.{name} RESTRICT')
