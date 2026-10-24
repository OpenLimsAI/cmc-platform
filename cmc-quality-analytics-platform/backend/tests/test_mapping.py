# -*- coding: utf-8 -*-
"""映射层单测（无需数据库）。"""
from app.services.mapping import attribute_mapping, data_type
from app.services.mapping.batch import extract_batch_order, extract_year_from_batch


def test_batch_order():
    assert extract_batch_order("007-201903F") == 201903
    assert extract_batch_order("PG1B20201104") == 20201104
    assert extract_batch_order("NP520250501A") == 20250501
    assert extract_batch_order("garbage") == 0


def test_batch_year():
    assert extract_year_from_batch("007-201903F") == 2019
    assert extract_year_from_batch("PG1B20201104") == 2020


def test_data_type_suggest():
    assert data_type.suggest_bucket("长期稳定性试验") == "Stability"
    assert data_type.suggest_bucket("常规检测") == "Release"
    assert data_type.suggest_bucket("方法开发") == "Exclude"
    assert data_type.suggest_bucket("") == "Exclude"


def test_data_type_classify_uses_csv_then_fallback():
    # CSV 已生成（app/config/test_type_buckets.csv）；这些经启发式建议落桶
    assert data_type.classify("稳定性试验") == "Stability"
    assert data_type.classify("常规检测") == "Release"
    # 排除桶/未知 → Unknown
    assert data_type.classify("某种全新方法XYZ") == "Unknown"


def test_attribute_map_known_and_unknown():
    # 草稿映射存在的高频项
    assert attribute_mapping.map_name("聚合体峰面积之和") == "sec_aggregate_pct"
    assert attribute_mapping.is_pct("聚合体峰面积之和") is True
    assert attribute_mapping.map_name("表达量") == "expression_titer"
    assert attribute_mapping.is_pct("表达量") is False
    # 未映射
    assert attribute_mapping.map_name("不存在的检测项") is None
