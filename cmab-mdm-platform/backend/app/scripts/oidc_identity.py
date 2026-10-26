"""Privileged operator CLI: explicit subject to existing numeric MDM user mapping.

No user is created and no roles/passwords are copied from Casdoor. Database and
issuer must be named explicitly; this CLI does not authorize production changes.
"""
import argparse
import asyncio
import json
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.domains.auth.models import User
from app.domains.auth.oidc.service import OIDCService


async def apply(args):
    actual = urlsplit(settings.DATABASE_URL).path.lstrip("/")
    if args.database != actual or args.issuer != settings.MDM_OIDC_ISSUER_URL:
        raise ValueError("Explicit database or issuer does not match runtime configuration")
    async with AsyncSessionLocal() as db:
        actor = (await db.execute(select(User).options(selectinload(User.roles)).where(
            User.user_id == args.actor_id, User.deleted_at.is_(None)))).scalar_one()
        service = OIDCService(db)
        identity = await service.bind_identity(args.subject, args.user_id, actor=actor, reason=args.reason)
        print(json.dumps({"identity_id": identity.identity_id, "user_id": identity.user_id, "active": identity.active}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--actor-id", type=int, required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(apply(args))
    except Exception:
        # Provider errors/connection details must never become CLI credential output.
        raise SystemExit("Identity mapping not applied; verify target, explicit identity and authorized local actor") from None


if __name__ == "__main__":
    main()
