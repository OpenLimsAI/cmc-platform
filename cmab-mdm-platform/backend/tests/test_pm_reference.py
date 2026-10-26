"""PM reference boundary unit tests; run via isolated scripts/run_tests.sh only."""
import httpx
import pytest
from app.domains.prs.pm_reference import PMReferenceClient, ReferenceUnavailableError, safe_base_url


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "https://user:secret@example.test", "https://pm.test/?token=x",
    "https://pm.test/#x", "//pm.test", "http://remote.test", "https://pm.test/../evil",
    "https://pm.test/\\evil", "https://pm.test/%2f%2fevil", "https://pm.test/\n",
])
def test_reject_unsafe_url(url):
    with pytest.raises(ValueError):
        safe_base_url(url)


def test_base_url_preserves_deployment_path():
    assert safe_base_url("http://localhost:5175/") == "http://localhost:5175"
    assert safe_base_url("https://example.test/mdm/") == "https://example.test/mdm"


async def test_reference_is_verified_and_uses_only_its_own_token():
    def respond(request):
        assert request.headers["authorization"] == "Bearer contract-test-only"
        assert request.url.path == "/api/v1/projects/pm-1/integration-reference"
        return httpx.Response(200, json={"id": "pm-1", "code": "PM-1", "name": "执行项目", "status": "活跃", "bindable": True})
    client = PMReferenceClient("https://pm.test", "contract-test-only", transport=httpx.MockTransport(respond))
    result = await client.get("pm-1")
    assert result.id == "pm-1"
    assert "contract-test-only" not in result.model_dump_json()


@pytest.mark.parametrize("status", [301, 401, 403, 500])
async def test_remote_failure_is_closed(status):
    client = PMReferenceClient("https://pm.test", "contract-test-only", transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    with pytest.raises(ReferenceUnavailableError):
        await client.get("pm-1")


async def test_missing_configuration_and_mismatched_reference():
    with pytest.raises(ReferenceUnavailableError):
        await PMReferenceClient("", "").get("pm-1")
    client = PMReferenceClient("https://pm.test", "contract-test-only", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"id": "other", "code": "PM-2", "name": "错误目标", "status": "活跃", "bindable": True})))
    with pytest.raises(ReferenceUnavailableError):
        await client.get("pm-1")


async def test_total_deadline_includes_streaming_body():
    import asyncio

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.1)
            yield '{"id":"pm-1","code":"PM-1","name":"test","status":"活跃","bindable":true}'.encode()

    client = PMReferenceClient("https://pm.test", "contract-test-only", transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowBody())))
    client.deadline_seconds = 0.01
    with pytest.raises(ReferenceUnavailableError):
        await client.get("pm-1")
