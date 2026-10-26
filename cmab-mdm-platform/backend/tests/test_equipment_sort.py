"""设备列表：部门优先、编号升序，排序须在分页之前完成。"""

import pytest

LIST_SORT = "department,equipment_no,equipment_code"


async def _create_equipment(admin_client, name, department, equipment_no):
    response = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": name,
            "category": "通用实验室设备",
            "department": department,
            "equipment_no": equipment_no,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["equipment_code"]


async def _list_equipment(admin_client, query, **params):
    response = await admin_client.get(
        "/api/v1/equipments",
        params={"q": query, "sort": LIST_SORT, "page_size": 100, **params},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["data"], body["meta"]["pagination"]["total"]


@pytest.mark.asyncio
async def test_equipment_department_number_sort_pagination(admin_client, unique_suffix):
    """乱序录入、重复编号、跨页和部门筛选均保持同一排序。"""
    query = f"pytest-sort-{unique_suffix}"
    records = [
        ("B部门", "CC1-SC-001"),
        ("A部门", "CC1-SC-010"),
        ("A部门", "CC1-SC-002"),
        ("B部门", "CC1-SC-002"),
        ("A部门", "CC1-SC-002"),
        ("A部门", "CC1-SC-001"),
    ]
    codes = []
    for index, (department, number) in enumerate(records):
        codes.append(
            await _create_equipment(admin_client, f"{query}-{index}", department, number)
        )

    expected = [codes[index] for index in (5, 2, 4, 1, 0, 3)]
    items, total = await _list_equipment(admin_client, query)
    assert total == len(records)
    assert [item["equipment_code"] for item in items] == expected

    paged_codes = []
    for page in range(1, 4):
        items, total = await _list_equipment(admin_client, query, page=page, page_size=2)
        assert total == len(records)
        assert len(items) == 2
        paged_codes.extend(item["equipment_code"] for item in items)
    assert paged_codes == expected

    items, total = await _list_equipment(admin_client, query, department="A部门")
    assert total == 4
    assert [item["equipment_code"] for item in items] == expected[:4]


@pytest.mark.asyncio
@pytest.mark.parametrize("descending", [False, True])
async def test_equipment_sort_blanks_last(admin_client, unique_suffix, descending):
    """NULL、空串及空格都排末尾；排序忽略首尾空格但不改写原值。"""
    query = f"pytest-blank-sort-{unique_suffix}"
    records = [
        (None, "CC1-SC-003"),
        ("B部门", "CC1-SC-001"),
        ("A部门", None),
        ("", "CC1-SC-002"),
        ("A部门", ""),
        ("   ", "CC1-SC-001"),
        ("A部门", "   "),
        (" A部门 ", " CC1-SC-002 "),
        ("A部门", "CC1-SC-001"),
    ]
    codes = []
    for index, (department, number) in enumerate(records):
        codes.append(
            await _create_equipment(admin_client, f"{query}-{index}", department, number)
        )

    sort = "-department,-equipment_no,equipment_code" if descending else LIST_SORT
    order = (1, 7, 8, 2, 4, 6, 0, 3, 5) if descending else (8, 7, 2, 4, 6, 1, 5, 3, 0)
    items, total = await _list_equipment(admin_client, query, sort=sort)
    assert total == len(records)
    assert [item["equipment_code"] for item in items] == [codes[index] for index in order]

    by_code = {item["equipment_code"]: item for item in items}
    for index, (department, number) in enumerate(records):
        assert by_code[codes[index]]["department"] == department
        assert by_code[codes[index]]["equipment_no"] == number
