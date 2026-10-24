# -*- coding: utf-8 -*-
"""Avoid three-way joins in water sample counts; retain the complete contract."""
from alembic import op

revision = 'analytics_water_mart_perf_1009'
down_revision = 'analytics_water_mart_20261009'
branch_labels = None
depends_on = None

SAMPLE_SQL = r"""WITH grouped AS (
    SELECT source_system, sample_id, water_type, sample_status, sample_name, samplepoint_id, samplepoint_code, samplepoint_name, samplepoint_mapping_source, samplepoint_mapping_scope, samplepoint_source_moddt, samplepoint_extracted_at, trend_at, trend_date_source, collectiondt, sample_eventdt, receiveddt, sample_createdt,
      count(*) AS result_count,
      count(*) FILTER (WHERE plot_eligible) AS trend_result_count,
      count(*) FILTER (WHERE result_role = 'conclusion') AS conclusion_count,
      count(DISTINCT jsonb_build_array(sdcid,keyid1,keyid2,keyid3,paramlistid,paramlistversionid,variantid,dataset)) AS dataset_count,
      max(staging_loaded_at) AS staging_loaded_at
    FROM mart.v_water_result GROUP BY source_system, sample_id, water_type, sample_status, sample_name, samplepoint_id, samplepoint_code, samplepoint_name, samplepoint_mapping_source, samplepoint_mapping_scope, samplepoint_source_moddt, samplepoint_extracted_at, trend_at, trend_date_source, collectiondt, sample_eventdt, receiveddt, sample_createdt
), checked AS (
    SELECT g.*,count(*) OVER (PARTITION BY source_system,sample_id) AS attribute_versions
    FROM grouped g
)
SELECT source_system, sample_id, water_type, sample_status, sample_name, samplepoint_id, samplepoint_code, samplepoint_name, samplepoint_mapping_source, samplepoint_mapping_scope, samplepoint_source_moddt, samplepoint_extracted_at, trend_at, trend_date_source, collectiondt, sample_eventdt, receiveddt, sample_createdt, result_count, trend_result_count, conclusion_count, dataset_count, staging_loaded_at, 'water_mart_v1'::text AS mart_rule_version
FROM checked WHERE attribute_versions = 1"""


def upgrade():
    bind = op.get_bind()
    if bind.exec_driver_sql('SELECT current_database()').scalar() not in ('cmc_analytics','cmc_analytics_training'):
        raise RuntimeError('Unexpected water mart migration database')
    bind.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    # Same columns/types/grain; preserve SELECT grants and downstream identities.
    bind.exec_driver_sql('CREATE OR REPLACE VIEW mart.v_water_sample WITH (security_barrier=true) AS ' + SAMPLE_SQL)


def downgrade():
    # Reuse the immutable initial definition, without duplicating its contract.
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('water_mart_original', Path(__file__).with_name('20261009_analytics_water_mart.py'))
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    query = dict(original.VIEW_DEFINITIONS)['v_water_sample']
    op.get_bind().exec_driver_sql('CREATE OR REPLACE VIEW mart.v_water_sample WITH (security_barrier=true) AS ' + query)
