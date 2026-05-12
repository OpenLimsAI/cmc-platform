"""
同一性判定（:check-sameness）测试
"""
import pytest


# 与种子 SUB-0000001 的 HC 完全一致
SEED_HC_SUB001 = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTISADTSKNTAYLQMNSLRAEDTAVYYCSRWGGDGFYAMDYWGQGTLVTVSS"
)
SEED_LC_SUB001 = (
    "DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFTLTISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK"
)


@pytest.mark.asyncio
async def test_empty_input_returns_empty(admin_client):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["matches"] == []


@pytest.mark.asyncio
async def test_exact_dual_chain_match_confidence_one(admin_client):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={
            "substance_type": "mab",
            "heavy_chain_sequence": SEED_HC_SUB001,
            "light_chain_sequence": SEED_LC_SUB001,
        },
    )
    matches = r.json()["data"]["matches"]
    sub001 = next((m for m in matches if m["substance_code"] == "SUB-0000001"), None)
    assert sub001 is not None
    assert sub001["confidence"] == 1.0
    assert set(sub001["matched_fields"]) == {"heavy_chain_sequence", "light_chain_sequence"}


@pytest.mark.asyncio
async def test_single_chain_match_confidence_85(admin_client):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={
            "substance_type": "mab",
            "heavy_chain_sequence": SEED_HC_SUB001,
            "light_chain_sequence": "ZZZNOTAMATCHZZZ",
        },
    )
    matches = r.json()["data"]["matches"]
    sub001 = next((m for m in matches if m["substance_code"] == "SUB-0000001"), None)
    assert sub001 is not None
    assert sub001["confidence"] == 0.85
    assert sub001["matched_fields"] == ["heavy_chain_sequence"]


@pytest.mark.asyncio
async def test_internal_code_only_confidence_06(admin_client):
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab", "internal_code": "CMAB-101"},
    )
    matches = r.json()["data"]["matches"]
    assert any(m["substance_code"] == "SUB-0000001" and m["confidence"] == 0.6 for m in matches)


@pytest.mark.asyncio
async def test_sequence_with_whitespace_normalized(admin_client):
    """带换行 / 空格的序列应被归一化到与原序列同 hash"""
    spaced = SEED_HC_SUB001[:50] + "\n" + SEED_HC_SUB001[50:] + " "
    r = await admin_client.post(
        "/api/v1/substances:check-sameness",
        json={"substance_type": "mab", "heavy_chain_sequence": spaced},
    )
    matches = r.json()["data"]["matches"]
    assert any(m["substance_code"] == "SUB-0000001" for m in matches), \
        "归一化后的序列应能匹配上 SUB-0000001"
