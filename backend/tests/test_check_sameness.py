"""
同一性判定（:check-sameness）测试

自建 substance fixture：每个用例创建一条带唯一 HC/LC 序列的 mab 物质，
再断言 :check-sameness 能按预期 confidence 命中它。不依赖任何预置种子，
因此对 dev DB 数据漂移（如 demo 数据集重置）免疫。
"""
import uuid

import pytest
import pytest_asyncio

# 用于把 uuid hex（0-9a-f，16 进制）映射为合法氨基酸单字母，拼出唯一序列尾巴
_HEX_TO_AA = str.maketrans("0123456789abcdef", "ACDEFGHIKLMNPQRS")

# 固定可读前缀（合法 AA），后缀保证全库唯一
_HC_PREFIX = "EVQLVESGGGLVQPGGSLRLSCAAS"
_LC_PREFIX = "DIQMTQSPSSLSASVGDRVTITCRAS"


def _unique_seq(prefix: str) -> str:
    tail = uuid.uuid4().hex.translate(_HEX_TO_AA)
    return prefix + tail


@pytest_asyncio.fixture
async def mab_fixture(admin_client):
    """创建一条带唯一 HC/LC 的 mab 物质，返回其 code 与序列。"""
    hc = _unique_seq(_HC_PREFIX)
    lc = _unique_seq(_LC_PREFIX)
    internal_code = f"SAME-{uuid.uuid4().hex[:8]}"
    resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": internal_code,
            "preferred_name": "check-sameness fixture",
            "protein": {
                "heavy_chain_sequence": hc,
                "light_chain_sequence": lc,
            },
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["substance_code"]
    return {"code": code, "hc": hc, "lc": lc, "internal_code": internal_code}


@pytest.mark.asyncio
async def test_empty_input_returns_empty(admin_client):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["matches"] == []


@pytest.mark.asyncio
async def test_exact_dual_chain_match_confidence_one(admin_client, mab_fixture):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={
            "substance_type": "mab",
            "heavy_chain_sequence": mab_fixture["hc"],
            "light_chain_sequence": mab_fixture["lc"],
        },
    )
    matches = r.json()["data"]["matches"]
    hit = next((m for m in matches if m["substance_code"] == mab_fixture["code"]), None)
    assert hit is not None
    assert hit["confidence"] == 1.0
    assert set(hit["matched_fields"]) == {"heavy_chain_sequence", "light_chain_sequence"}


@pytest.mark.asyncio
async def test_single_chain_match_confidence_85(admin_client, mab_fixture):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={
            "substance_type": "mab",
            "heavy_chain_sequence": mab_fixture["hc"],
            "light_chain_sequence": "ZZZNOTAMATCHZZZ",
        },
    )
    matches = r.json()["data"]["matches"]
    hit = next((m for m in matches if m["substance_code"] == mab_fixture["code"]), None)
    assert hit is not None
    assert hit["confidence"] == 0.85
    assert hit["matched_fields"] == ["heavy_chain_sequence"]


@pytest.mark.asyncio
async def test_internal_code_only_confidence_06(admin_client, mab_fixture):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab", "internal_code": mab_fixture["internal_code"]},
    )
    matches = r.json()["data"]["matches"]
    assert any(
        m["substance_code"] == mab_fixture["code"] and m["confidence"] == 0.6
        for m in matches
    )


@pytest.mark.asyncio
async def test_sequence_with_whitespace_normalized(admin_client, mab_fixture):
    """带换行 / 空格的序列应被归一化到与原序列同 hash"""
    hc = mab_fixture["hc"]
    spaced = hc[:20] + "\n" + hc[20:] + " "
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab", "heavy_chain_sequence": spaced},
    )
    matches = r.json()["data"]["matches"]
    assert any(m["substance_code"] == mab_fixture["code"] for m in matches), \
        "归一化后的序列应能匹配上自建物质"
