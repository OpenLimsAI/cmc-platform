"""批量导入用户（2026-09-10，首用于验证部 5 人）。

输入一个 CSV / TSV 名单（首行表头，中英文表头都认）：
    姓名, 工号, 邮箱, 角色[, 部门][, 职位]
    - 工号 = 登录账号（auth.user.username，全公司用工号登录）
    - 角色：中文角色名或角色码，多个用 、 , ， / 分隔（按 auth.role.role_name / role_code 匹配）
    - 部门：列里没有就用 --department 统一指定

行为：
    - 已存在的工号 / 邮箱：跳过并提示，不覆盖（幂等，可反复跑）
    - 新建：随机 16 位临时密码 + force_password_change=TRUE（首次登录强制改密），状态 active
    - 每人写一条 audit_log CREATE（entity auth.user，change_summary 含角色）
    - 结束打印「工号 | 姓名 | 临时密码」表，管理员通过安全渠道告知本人；临时密码不写库日志，
      但会出现在本次命令的终端输出里，注意别把终端记录转发出去
    - --dry-run 只校验和预览，不写库

运行：
    Mac 容器内：docker exec -i cmab-mdm-backend python -m app.scripts.import_users --file - --department QV < 名单.csv
    Linux：cd /opt/cmab-mdm-platform/backend && .venv/bin/python -m app.scripts.import_users --file /tmp/名单.csv --department QV
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import re
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.admin_service import _generate_temp_password
from app.domains.auth.models import Role, User, UserRole

HEADER_ALIASES = {
    "full_name": {"姓名", "name", "full_name"},
    "username": {"工号", "username", "employee_id", "账号"},
    "email": {"邮箱", "email", "mail"},
    "roles": {"角色", "roles", "role"},
    "department": {"部门", "department", "dept"},
    "title": {"职位", "title"},
}
_ROLE_SPLIT = re.compile(r"[、,，/;；\s]+")


def _normalize_header(h: str) -> str | None:
    h = h.strip().lower()
    for key, names in HEADER_ALIASES.items():
        if h in {n.lower() for n in names}:
            return key
    return None


def read_rows(text: str) -> list[dict[str, str]]:
    sample = text[:2048]
    delim = "\t" if sample.count("\t") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise SystemExit("名单为空")
    keys = [_normalize_header(h) for h in rows[0]]
    unknown = [h for h, k in zip(rows[0], keys, strict=False) if k is None]
    if unknown:
        print(f"⚠ 忽略无法识别的列: {unknown}")
    out = []
    for r in rows[1:]:
        d = {k: (r[i].strip() if i < len(r) else "") for i, k in enumerate(keys) if k}
        out.append(d)
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description="批量导入 MDM 用户")
    ap.add_argument("--file", required=True, help="CSV/TSV 路径，- 表示标准输入")
    ap.add_argument("--department", default=None, help="名单没有部门列时统一使用的部门")
    ap.add_argument("--actor", default="admin", help="操作人账号（created_by / 审计），默认 admin")
    ap.add_argument("--dry-run", action="store_true", help="只校验预览，不写库")
    args = ap.parse_args()

    if args.file == "-":
        # Excel 导出的 CSV 带 BOM，走标准输入时没有 utf-8-sig 帮忙去掉，首列表头会变成 "\ufeff姓名"
        text = sys.stdin.read().lstrip("\ufeff")
    else:
        with open(args.file, encoding="utf-8-sig") as fh:
            text = fh.read()
    rows = read_rows(text)

    async with AsyncSessionLocal() as db:
        actor = (
            await db.execute(select(User).where(User.username == args.actor, User.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if actor is None:
            raise SystemExit(f"操作人账号 {args.actor} 不存在")

        roles = (await db.execute(select(Role).where(Role.deleted_at.is_(None)))).scalars().all()
        role_by_name = {r.role_name: r for r in roles}
        role_by_code = {r.role_code: r for r in roles}

        # ---- 校验 ----
        plan: list[tuple[dict, list[Role]]] = []
        errors: list[str] = []
        for i, row in enumerate(rows, start=2):
            missing = [k for k in ("full_name", "username", "email") if not row.get(k)]
            if missing:
                errors.append(f"第 {i} 行缺少 {missing}: {row}")
                continue
            dept = row.get("department") or args.department
            if not dept:
                errors.append(f"第 {i} 行没有部门，且未指定 --department: {row['username']}")
                continue
            row["department"] = dept
            resolved: list[Role] = []
            for name in _ROLE_SPLIT.split(row.get("roles", "")):
                if not name:
                    continue
                r = role_by_name.get(name) or role_by_code.get(name.upper())
                if r is None:
                    errors.append(f"第 {i} 行角色「{name}」在 auth.role 里找不到（{row['username']}）")
                elif r not in resolved:
                    resolved.append(r)
            plan.append((row, resolved))
        if errors:
            print("✗ 名单有误，未写入任何数据：")
            for e in errors:
                print("   " + e)
            return 1

        # ---- 逐条导入 ----
        created: list[tuple[str, str, str]] = []
        skipped: list[str] = []
        for row, rlist in plan:
            exist = (
                await db.execute(
                    select(User).where(
                        (User.username == row["username"]) | (User.email == row["email"]),
                        User.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            if exist is not None:
                skipped.append(f"{row['username']} {row['full_name']}（已存在：{exist.username} / {exist.email}）")
                continue
            codes = [r.role_code for r in rlist]
            if args.dry_run:
                created.append((row["username"], row["full_name"], f"(dry-run) 角色={codes} 部门={row['department']}"))
                continue
            temp_pw = _generate_temp_password(16)
            now = datetime.now(UTC)
            user = User(
                username=row["username"],
                email=row["email"],
                password_hash=hash_password(temp_pw),
                full_name=row["full_name"],
                department=row["department"],
                title=row.get("title") or None,
                status="active",
                password_changed_at=now,
                password_expires_at=now + timedelta(days=7),
                force_password_change=True,
                created_by=actor.user_id,
                updated_by=actor.user_id,
            )
            db.add(user)
            await db.flush()
            for r in rlist:
                db.add(UserRole(user_id=user.user_id, role_id=r.role_id, granted_by=actor.user_id))
            db.add(
                AuditLog(
                    user_id=actor.user_id,
                    username=actor.username,
                    action="CREATE",
                    entity_schema="auth",
                    entity_table="user",
                    entity_id=user.user_id,
                    entity_code=user.username,
                    change_summary=f"批量导入用户 {user.username}（{user.full_name}，部门 {user.department}，角色 {codes}）",
                    extra={"source": "app.scripts.import_users", "roles": codes, "department": user.department},
                )
            )
            await db.flush()
            created.append((user.username, user.full_name, temp_pw))

        if args.dry_run:
            await db.rollback()
        else:
            await db.commit()
    await engine.dispose()

    print(f"\n{'（预览，未写库）' if args.dry_run else ''}新建 {len(created)} 人，跳过 {len(skipped)} 人")
    for s in skipped:
        print("   跳过: " + s)
    if created:
        print("\n工号      姓名        " + ("说明" if args.dry_run else "临时密码（首次登录强制改密，请安全告知本人）"))
        for u, n, pw in created:
            print(f"{u:<9} {n:<10} {pw}")
    # 确认角色/权限写入（非 dry-run）
    if created and not args.dry_run:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(User).options(selectinload(User.roles)).where(User.username.in_([u for u, _, _ in created]))
            )
            for u in res.scalars():
                print(f"   ✓ {u.username} {u.full_name} 部门={u.department} 角色={[r.role_code for r in u.roles]}")
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
