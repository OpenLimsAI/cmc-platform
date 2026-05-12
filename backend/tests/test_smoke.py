"""
最简烟雾测试：确保应用能启动、健康检查可用
完整测试套件由 conftest.py 中的 fixture 配合其他 test_*.py 提供。
"""
import pytest
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(base_url=BASE_URL) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token():
    async with AsyncClient(base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/substances")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 40104
