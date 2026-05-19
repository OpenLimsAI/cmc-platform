"""
文件: backend/tests/test_import_commit.py
用途: 正式导入提交的一致性测试
覆盖:
    - 提交阶段重新检查重复代码
    - 失败行不会顺手写入分类字典
"""
from __future__ import annotations

from sqlalchemy import text


def test_import_commit_duplicate_code_marks_failed_and_keeps_dict_clean(client, db):
    resp = client.post("/api/import/materials/commit", json={
        "file_name": "duplicate.xlsx",
        "auto_create_units": True,
        "rows": [
            {
                "material_code": "IMP001",
                "category": "成功分类",
                "name_cn": "导入物料 A",
                "unit": "支",
            },
            {
                "material_code": "IMP001",
                "category": "失败分类",
                "name_cn": "导入物料 B",
                "unit": "支",
            },
        ],
    })

    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["inserted_rows"] == 1
    assert body["failed_rows"] == 1

    material_count = db.execute(text(
        "SELECT count(*) FROM material WHERE material_code='IMP001'"
    )).scalar_one()
    assert material_count == 1

    failed_category = db.execute(text(
        "SELECT 1 FROM category_dict WHERE category='失败分类'"
    )).first()
    assert failed_category is None
