# _group_clause：检验组过滤内联为 ARRAY 字面量（asyncpg 绑不了 NULL list 参数的规避写法）
from app.services.lims.stats_service import _group_clause


def test_empty_groups_no_filter():
    assert _group_clause(None) == ("TRUE", {})
    assert _group_clause([]) == ("TRUE", {})


def test_groups_inlined_as_array_literal():
    sql, params = _group_clause(["TT1", "TT5"])
    assert sql == "group_id = ANY(ARRAY['TT1','TT5'])"
    assert params == {}


def test_single_quote_escaped_against_injection():
    # 恶意输入的单引号必须翻倍转义，不能拼出可逃逸的 SQL
    sql, _ = _group_clause(["T'T; DROP TABLE x;--"])
    assert "T''T" in sql
    # 除了字面量内部的转义引号外，不应出现能截断字符串的裸引号结构
    assert sql.count("ARRAY[") == 1
    assert sql.endswith("])")
