"""默认只读预览；--apply 显式结束仍有效的历史分支会话，不删除任何记录。"""
import argparse
import asyncio
import json

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import User
from app.domains.auth.refresh_branch_repair import affected_sessions, close_affected_sessions


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True, help='显式核对目标库名')
    parser.add_argument('--apply', action='store_true', help='显式执行；默认不写入')
    parser.add_argument('--actor', help='执行人 MDM 工号（执行模式必填，需 SYS_ADMIN）')
    parser.add_argument('--reason', help='执行原因（执行模式必填，保存到审计）')
    args = parser.parse_args()
    if args.apply and (not args.actor or not args.reason or not args.reason.strip()):
        parser.error('--apply 必须指定 --actor 与非空 --reason')
    try:
        async with AsyncSessionLocal() as db:
            if not args.apply:
                await db.execute(text('SET TRANSACTION READ ONLY'))
            database = (await db.execute(text('SELECT current_database()'))).scalar_one()
            if database != args.expected_database:
                raise RuntimeError('目标库与 --expected-database 不一致，未执行')
            report = {'database': database, 'mode': 'apply' if args.apply else 'preview'}
            if args.apply:
                actor = (await db.execute(select(User).where(
                    User.username == args.actor, User.deleted_at.is_(None), User.status == 'active',
                ).options(selectinload(User.roles)))).scalar_one_or_none()
                if actor is None or not any(role.role_code == 'SYS_ADMIN' for role in actor.roles):
                    raise RuntimeError('执行人必须是有效的 SYS_ADMIN，未执行')
                report.update(await close_affected_sessions(db, actor=actor, reason=args.reason))
                await db.commit()
            else:
                sessions = await affected_sessions(db)
                report.update({'affected_sessions': len(sessions),
                               'affected_accounts': len({s['user_id'] for s in sessions}),
                               'branch_evidence_records': sum(s['branches'] for s in sessions)})
                await db.rollback()
            print(json.dumps(report, ensure_ascii=False))
    finally:
        await engine.dispose()
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
