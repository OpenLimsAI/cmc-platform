"""外部 HTTP 客户端封装（只读 GET）—— httpx + tenacity

首个用户：靶点域批量预填脚本（ChEMBL / UniProt）。设计要点：
  - 域名白名单：只允许访问显式列出的主机，防止脚本/服务被当成通用代理
  - 超时 + 对 5xx / 429 / 网络错误做指数退避重试（4xx 直接失败，404 返回 None）
  - Linux 生产直连出网、无需代理（2026-08-18 上机验证）；Mac 开发机有 ClashX，
    默认 trust_env=True 让 httpx 按环境变量走代理，脚本可通过 --no-proxy 关掉
  - 每次调用记 loguru（自动带 request_id / user_id 上下文），供审计/排障
  - 测试用 httpx.MockTransport 注入，测试不许真出网
"""
from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RETRIES = 3
USER_AGENT = "cmab-mdm-platform/target-prefill (read-only GET; internal use)"


class ExternalHttpError(Exception):
    """外部调用最终失败（重试耗尽 / 4xx / 白名单拒绝）"""

    def __init__(self, url: str, status: int | None, detail: str):
        super().__init__(f"{url} -> HTTP {status}: {detail}")
        self.url, self.status, self.detail = url, status, detail


class _RetryableError(Exception):
    """内部标记：5xx / 429 / 网络错误 → 交给 tenacity 重试"""


class ExternalHttpClient:
    """异步只读 GET 客户端。用法：

        async with ExternalHttpClient(allowed_hosts={"www.ebi.ac.uk"}) as c:
            status, data = await c.get_json("https://www.ebi.ac.uk/chembl/api/data/status.json")
    """

    def __init__(
        self,
        allowed_hosts: Iterable[str],
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        trust_env: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.retries = retries
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s),
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            trust_env=trust_env,
            transport=transport,
            follow_redirects=True,
        )
        self.calls: list[dict[str, Any]] = []  # 调用台账（脚本产物里存档）

    async def __aenter__(self) -> ExternalHttpClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _check_host(self, url: str) -> None:
        host = (httpx.URL(url).host or "").lower()
        if host not in self.allowed_hosts:
            raise ExternalHttpError(url, None, f"host {host!r} 不在白名单 {sorted(self.allowed_hosts)}")

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> tuple[int, Any]:
        """GET 并解析 JSON。返回 (status, data)；404 → (404, None)；其余失败抛 ExternalHttpError。"""
        self._check_host(url)
        attempt = 0
        try:
            async for attempt_state in AsyncRetrying(
                stop=stop_after_attempt(self.retries),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type(_RetryableError),
                reraise=False,
            ):
                with attempt_state:
                    attempt += 1
                    t0 = time.monotonic()
                    try:
                        resp = await self._client.get(url, params=params)
                    except (httpx.TimeoutException, httpx.NetworkError) as e:
                        self._log(url, None, t0, attempt, error=f"{type(e).__name__}: {e}")
                        raise _RetryableError(str(e)) from e
                    status = resp.status_code
                    if status == 404:
                        self._log(url, 404, t0, attempt)
                        return 404, None
                    if status >= 500 or status == 429:
                        self._log(url, status, t0, attempt, error=resp.text[:200])
                        raise _RetryableError(f"HTTP {status}")
                    if status >= 400:
                        self._log(url, status, t0, attempt, error=resp.text[:200])
                        raise ExternalHttpError(url, status, resp.text[:500])
                    self._log(url, status, t0, attempt)
                    return status, resp.json()
        except RetryError as e:
            last = e.last_attempt.exception()
            raise ExternalHttpError(url, None, f"重试 {self.retries} 次仍失败：{last}") from e
        raise ExternalHttpError(url, None, "unreachable")  # pragma: no cover

    def _log(self, url: str, status: int | None, t0: float, attempt: int, error: str | None = None) -> None:
        rec = {
            "url": url,
            "http_status": status,
            "elapsed_ms": round((time.monotonic() - t0) * 1000),
            "attempt": attempt,
            "ok": error is None,
            "error": error,
        }
        self.calls.append(rec)
        logger.bind(**rec).log("WARNING" if error else "INFO", "external http get")
