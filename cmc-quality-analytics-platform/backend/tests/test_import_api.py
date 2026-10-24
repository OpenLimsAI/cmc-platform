"""预览 API 的真实 JWT/权限、请求界限与原值保真；仅合成数据，无数据库。"""
from io import BytesIO
from secrets import token_urlsafe
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
from openpyxl import Workbook, load_workbook
import pytest

from app.api.v1 import imports
from app.api.v1.router import api_router
from app.core.config import Settings, get_auth_settings
from app.core.database import get_session
from app.core.envelope import register_exception_handlers


@pytest.fixture
def auth_settings():
    return Settings(
        _env_file=None, environment="test", auth_required=True,
        jwt_secret_key=token_urlsafe(48), read_roles=["TEST_READ"], import_preview_roles=["TEST_PREVIEW"],
    )


@pytest.fixture
def client(auth_settings):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_auth_settings] = lambda: auth_settings

    def no_database():
        raise AssertionError("这些权限/预览测试不得获取数据库连接")

    app.dependency_overrides[get_session] = no_database
    with TestClient(app) as test_client:
        yield test_client


def bearer(settings, roles=("TEST_PREVIEW",)):
    token = jwt.encode({
        "sub": "test-subject", "username": "test-employee", "full_name": "测试员工",
        "roles": list(roles), "type": "access", "exp": int(time.time()) + 120,
    }, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.title = "质量数据"
    sheet.append(["project_code", "batch_number", "attribute", "value", "unit"])
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def form(content):
    return {"files": {"file": ("sample.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            "data": {"template_code": "qap_long_preview_v1"}}


def test_auth_checked_before_reading_any_upload_bytes(client, monkeypatch):
    async def forbidden_read(_request):
        raise AssertionError("未登录不应读取请求体")

    monkeypatch.setattr(imports, "_bounded_request", forbidden_read)
    response = client.post("/api/v1/imports/preview", content=b"malformed")
    assert response.status_code == 401
    assert response.json()["errors"]


def test_read_role_does_not_grant_preview_and_empty_role_does_not_grant_read(client, auth_settings):
    response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings, ["TEST_READ"]), content=b"x")
    assert response.status_code == 403
    response = client.get("/api/v1/meta/projects", headers=bearer(auth_settings, []))
    assert response.status_code == 403


def test_preview_is_only_structure_not_import_and_actor_is_from_token(client, auth_settings):
    content = workbook([("P", "0001-a", "主峰", 0.98, "%"), ("P", "0001-a", "残留", "<LOD", "ng/ml")])
    response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings), **form(content))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert data["actor"] == {"username": "test-employee", "full_name": "测试员工"}
    assert data["preview_only"] and data["preview"]["structure_valid"]
    assert not data["preview"]["can_commit"]
    assert data["preview"]["business_validation"] == "pending"
    assert data["preview"]["rows"][0]["cells"][3]["value"] == 0.98
    assert data["preview"]["rows"][1]["cells"][3]["value"] == "<LOD"
    assert data["preview"]["rows"][0]["row_number"] == 2
    assert "Authorization" not in response.text and "test-subject" not in response.text
    assert client.post("/api/v1/imports/commit", headers=bearer(auth_settings)).status_code == 404


def test_truncated_display_cannot_hide_errors_in_later_rows(client, auth_settings, monkeypatch):
    monkeypatch.setattr(imports, "MAX_PREVIEW_ROWS", 1)
    monkeypatch.setattr(imports, "MAX_PREVIEW_ISSUES", 1)
    content = workbook([("P", "A", "X", 1, None), ("P", "B" * 33, "X", 2, None), ("P", None, "X", 3, None)])
    response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings), **form(content))
    data = response.json()["data"]
    assert data["total_row_count"] == 3 and len(data["preview"]["rows"]) == 1
    assert data["total_issue_count"] == 2 and len(data["preview"]["issues"]) == 1
    assert data["rows_truncated"] and data["issues_truncated"]
    assert not data["preview"]["structure_valid"]


def test_client_cannot_supply_trusted_actor_or_enable_commit(client, auth_settings):
    payload = form(workbook([("P", "A", "X", 1, "%")]))
    payload["data"]["actor_username"] = "forged"
    response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings), **payload)
    assert response.status_code in {400, 422}
    assert "forged" not in response.text


def test_actual_body_limit_applies_to_false_content_length(client, auth_settings, monkeypatch):
    monkeypatch.setattr(imports, "MAX_BODY_BYTES", 100)
    headers = {**bearer(auth_settings), "Content-Length": "1", "Content-Type": "multipart/form-data; boundary=x"}
    response = client.post("/api/v1/imports/preview", headers=headers, content=b"x" * 101)
    assert response.status_code == 413
    assert response.json()["errors"]


def test_multiple_files_and_unknown_template_rejected(client, auth_settings):
    response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings),
                           files=[("file", ("a.xlsx", b"a")), ("file", ("b.xlsx", b"b"))],
                           data={"template_code": "qap_long_preview_v1"})
    assert response.status_code == 400
    payload = form(workbook([("P", "A", "X", 1, "%")]))
    payload["data"]["template_code"] = "not-a-template"
    assert client.post("/api/v1/imports/preview", headers=bearer(auth_settings), **payload).status_code == 422


def test_template_download_has_no_business_rows_and_requires_preview_permission(client, auth_settings):
    path = "/api/v1/imports/templates/qap_long_preview_v1.xlsx"
    assert client.get(path).status_code == 401
    response = client.get(path, headers=bearer(auth_settings))
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content), read_only=True)
    try:
        sheet = book["质量数据"]
        assert sheet.max_row == 1
        assert [c.value for c in next(sheet.rows)] == ["project_code", "batch_number", "attribute", "value", "unit"]
    finally:
        book.close()


def test_preview_busy_response_does_not_parse_another_workbook(client, auth_settings):
    imports._PARSE_SLOT.acquire()
    try:
        response = client.post("/api/v1/imports/preview", headers=bearer(auth_settings),
                               **form(workbook([("P", "A", "X", 1, "%")])))
    finally:
        imports._PARSE_SLOT.release()
    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"


@pytest.mark.parametrize("roles,read_status,preview_status", [
    (["QAP_QC_GENERAL"], 200, 200),
    (["QAP_QA_RELEASE"], 200, 403),
    (["QAP_QC_GENERAL", "QAP_QA_RELEASE"], 200, 200),
    (["SYS_ADMIN"], 200, 200),
    (["READ_ONLY"], 403, 403),
    (["QC综合"], 403, 403),
    ([], 403, 403),
])
def test_confirmed_qc_qa_roles_protect_real_routes(client, monkeypatch, roles, read_status, preview_status):
    from app.api.v1.meta import _repo

    # 使用真实配置默认值与完整路由链；仓储替身保证不连接任何业务库。
    settings = Settings(_env_file=None, environment="test", auth_required=True, jwt_secret_key=token_urlsafe(48))
    client.app.dependency_overrides[get_auth_settings] = lambda: settings

    class NoDatabaseRepository:
        def list_projects(self, source_systems):
            return []

    client.app.dependency_overrides[_repo] = lambda: NoDatabaseRepository()
    headers = bearer(settings, roles)
    me = client.get("/api/v1/auth/me", headers=headers).json()["data"]
    assert me["can_read"] is (read_status == 200)
    assert me["can_preview"] is (preview_status == 200)
    assert me["can_commit"] is False
    assert client.get("/api/v1/meta/projects", headers=headers).status_code == read_status
    assert client.get("/api/v1/imports/capabilities", headers=headers).status_code == preview_status
    assert client.get("/api/v1/imports/templates/qap_long_preview_v1.xlsx", headers=headers).status_code == preview_status
    if preview_status == 403:
        async def reject_body(_request):
            raise AssertionError("QA或未授权角色不可读取上传文件内容")

        monkeypatch.setattr(imports, "_bounded_request", reject_body)
    response = client.post("/api/v1/imports/preview", headers=headers,
                           **form(workbook([("SYNTHETIC", "SYNTHETIC-001", "合成检测项", 0.98, "%")])))
    assert response.status_code == preview_status
    if preview_status == 200:
        assert response.json()["data"]["preview"]["can_commit"] is False
