"""
pytest 配置与共享 fixture

策略说明
========
Phase 1 用简化方案：测试**直接打 HTTP 到容器内运行的 uvicorn**（localhost:8000），
而不是 ASGITransport in-process 调用栈。原因：

  Starlette BaseHTTPMiddleware（我们用于 RequestIDMiddleware / AuditContextMiddleware）
  在 in-process 测试时与 asyncpg 连接池有已知的 event-loop 绑定冲突，导致每个测试
  在 teardown 时报 "attached to a different loop"。走真实 HTTP 后，uvicorn 进程
  持有一个稳定的 event loop，测试侧只是 HTTP 客户端，二者不共享 loop。

测试数据采用 uuid 后缀避免冲突；必要时 `make reset-db` 清理 dev DB。
Phase 2 将切换到独立 test DB + per-test 事务回滚。
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["data"]["access_token"]


class _AuthedClient:
    def __init__(self, client: AsyncClient, token: str):
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}

    def _merge(self, extra: dict | None) -> dict:
        if not extra:
            return self._headers
        return {**self._headers, **extra}

    async def get(self, url, **kw):
        extra = kw.pop("headers", None)
        return await self._client.get(url, headers=self._merge(extra), **kw)

    async def post(self, url, **kw):
        extra = kw.pop("headers", None)
        return await self._client.post(url, headers=self._merge(extra), **kw)

    async def put(self, url, **kw):
        extra = kw.pop("headers", None)
        return await self._client.put(url, headers=self._merge(extra), **kw)

    async def delete(self, url, **kw):
        # httpx.AsyncClient.delete 不直收 json 参数；走 request() 以支持 body
        extra = kw.pop("headers", None)
        return await self._client.request("DELETE", url, headers=self._merge(extra), **kw)


@pytest_asyncio.fixture
async def admin_client(http_client):
    token = await _login(http_client, "admin", "__REDACTED_SEED_PASSWORD_1__")
    return _AuthedClient(http_client, token)


@pytest_asyncio.fixture
async def readonly_client(http_client):
    token = await _login(http_client, "readonly", "__REDACTED_SEED_PASSWORD_4__")
    return _AuthedClient(http_client, token)


@pytest_asyncio.fixture
async def researcher_client(http_client):
    """CMC_RESEARCHER 角色：有 create/update 但没 approve/sign"""
    token = await _login(http_client, "researcher", "__REDACTED_SEED_PASSWORD_5__")
    return _AuthedClient(http_client, token)


@pytest.fixture
def unique_suffix() -> str:
    """每个测试拿到一个唯一后缀，用于构造不冲突的 internal_code 等"""
    return uuid.uuid4().hex[:8]
