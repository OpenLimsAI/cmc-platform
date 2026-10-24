"""经 MDM 验签和角色检查的内存预览入口；无保存/确认/发布端点。"""
from dataclasses import asdict, replace
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from starlette.datastructures import UploadFile
from starlette.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.auth import CurrentUser, require_import_preview
from app.core.envelope import envelope
from app.services.imports.preview import PreviewLimits, preview_workbook
from app.services.imports.templates import TEMPLATES, template_workbook

router = APIRouter(prefix="/imports", tags=["import-preview"])
LIMITS = PreviewLimits()
MAX_BODY_BYTES = LIMITS.max_file_bytes + 64 * 1024
MAX_PREVIEW_ROWS = 200
MAX_PREVIEW_ISSUES = 1000
_PARSE_SLOT = BoundedSemaphore(1)


def _capabilities() -> dict:
    return {
        "can_commit": False,
        "business_validation": "pending",
        "templates": [
            {
                "template_code": template.template_code, "version": template.version,
                "label": template.label, "sheet_name": template.sheet_name,
                "header_row": template.header_row, "label_row": template.label_row,
                "data_start_row": template.data_start_row,
                "headers": [column.source_header for column in template.columns],
                "max_file_bytes": LIMITS.max_file_bytes, "approval_state": "draft",
            }
            for template in TEMPLATES.values()
        ],
    }


@router.get("/capabilities")
async def capabilities(response: Response, _user: CurrentUser = Depends(require_import_preview)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return envelope(data=_capabilities())


@router.get("/templates/{template_code}.xlsx")
async def download_template(template_code: str, _user: CurrentUser = Depends(require_import_preview)) -> Response:
    template = TEMPLATES.get(template_code)
    if template is None:
        raise HTTPException(404, "找不到此预览模板")
    content = await run_in_threadpool(template_workbook, template)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{template.template_code}.xlsx"', "Cache-Control": "no-store"},
    )


async def _bounded_request(request: Request) -> Request:
    """先鉴权再读请求体，按实际字节限制，不信任 Content-Length。"""
    if request.headers.get("content-type", "").partition(";")[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "请使用表单上传一个 XLSX 文件")
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) < 0:
                raise ValueError
            if int(length) > MAX_BODY_BYTES:
                raise HTTPException(413, "上传请求超过大小限制")
        except ValueError as exc:
            raise HTTPException(400, "请求长度无效") from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, "上传请求超过大小限制")
        body.extend(chunk)
    consumed = False

    async def receive():
        nonlocal consumed
        if consumed:
            return {"type": "http.request", "body": b"", "more_body": False}
        consumed = True
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    return Request(request.scope, receive=receive)


def _parse_preview(content: bytes, filename: str, template_code: str):
    # 在线程内部持锁，客户端取消请求也不会在解析未结束时提前释放资源名额。
    if not _PARSE_SLOT.acquire(blocking=False):
        raise HTTPException(429, "正在处理另一个文件，请稍后重试", headers={"Retry-After": "2"})
    try:
        return preview_workbook(content, filename=filename, template=TEMPLATES[template_code], limits=LIMITS)
    finally:
        _PARSE_SLOT.release()


@router.post("/preview")
async def preview(request: Request, response: Response, user: CurrentUser = Depends(require_import_preview)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    # 不声明 File/Form 参数：FastAPI 先执行身份依赖，函数内才读取/解析 multipart。
    bounded = await _bounded_request(request)
    async with bounded.form(max_files=1, max_fields=1) as form:
        items = form.multi_items()
        if sorted(key for key, _ in items) != ["file", "template_code"]:
            raise HTTPException(422, "仅接受一个 file 和一个 template_code 字段")
        uploaded, template_code = form.get("file"), form.get("template_code")
        if not isinstance(uploaded, UploadFile) or not isinstance(template_code, str):
            raise HTTPException(422, "文件或模板字段格式不正确")
        if template_code not in TEMPLATES:
            raise HTTPException(422, "未知预览模板，不会自动猜测文件格式")
        content = await uploaded.read(LIMITS.max_file_bytes + 1)
        if not content or len(content) > LIMITS.max_file_bytes:
            raise HTTPException(413 if content else 422, "文件为空或超过大小限制")
        result = await run_in_threadpool(_parse_preview, content, uploaded.filename or "", template_code)
    # 已对完整文件校验；只转换响应切片，避免复制整个大预览。
    data = asdict(replace(result, rows=result.rows[:MAX_PREVIEW_ROWS], issues=result.issues[:MAX_PREVIEW_ISSUES]))
    data["structure_valid"] = result.structure_valid
    return envelope(data=jsonable_encoder({
        "preview": data,
        "actor": {"username": user.username, "full_name": user.full_name},
        "preview_only": True,
        "total_row_count": len(result.rows), "total_issue_count": len(result.issues),
        "rows_truncated": len(result.rows) > MAX_PREVIEW_ROWS,
        "issues_truncated": len(result.issues) > MAX_PREVIEW_ISSUES,
    }))
