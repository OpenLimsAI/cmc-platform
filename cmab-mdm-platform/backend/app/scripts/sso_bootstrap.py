"""Privileged empty-database bootstrap. Initial secrets never go to stdout/argv."""
import argparse
import asyncio
import hashlib
import json
import os
import secrets
import stat
import string
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domains.auth.oidc.config import checked_url
from app.domains.auth.oidc.protocol import OIDCError


class BootstrapAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
    subject: str = Field(min_length=1, max_length=255)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=128)

    @field_validator("subject", "full_name")
    @classmethod
    def exact_noncontrol_value(cls, value: str) -> str:
        if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Explicit identity fields must not contain control or boundary whitespace")
        return value


class BootstrapPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    database_host: str = Field(min_length=1, max_length=255)
    database_port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1, max_length=63, pattern=r"^[A-Za-z][A-Za-z0-9_]+$")
    issuer: str
    organization: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    operator_subject: str = Field(min_length=1, max_length=255)
    operator_ref: str = Field(min_length=5, max_length=255)
    reason: str = Field(min_length=5, max_length=1000)
    accounts: tuple[BootstrapAccount, ...] = Field(min_length=1, max_length=2)

    @field_validator("issuer")
    @classmethod
    def exact_issuer(cls, value: str) -> str:
        try:
            canonical = checked_url(value)
        except OIDCError:
            raise ValueError("Invalid explicit issuer") from None
        if canonical != value:
            raise ValueError("Issuer must match the exact configured canonical value")
        return value

    @field_validator("database_host")
    @classmethod
    def plain_host(cls, value: str) -> str:
        if value != value.strip() or any(c.isspace() or c in "/@?#\\" for c in value):
            raise ValueError("Invalid explicit database hostname")
        return value

    @field_validator("reason", "operator_ref")
    @classmethod
    def nonblank_operator_record(cls, value: str) -> str:
        if len(value.strip()) < 5 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("An explicit nonblank operator reference and reason are required")
        return value

    @model_validator(mode="after")
    def unique_explicit_accounts(self) -> Self:
        for key in ("subject", "username", "email"):
            values = [str(getattr(account, key)) for account in self.accounts]
            if key != "subject":
                values = [value.casefold() for value in values]
            if len(set(values)) != len(values):
                raise ValueError("Administrator targets must be distinct")
        if self.operator_subject not in {account.subject for account in self.accounts}:
            raise ValueError("The nominated authorizing administrator must be explicit")
        return self


def ensure_runtime_target(
    plan: BootstrapPlan, *, database_url: str, issuer: str, organization: str,
    native_enabled: bool, oidc_enabled: bool,
) -> None:
    try:
        parsed = urlsplit(database_url)
        matches = (parsed.scheme in {"postgresql", "postgresql+asyncpg", "postgresql+psycopg"}
                   and parsed.hostname == plan.database_host.lower()
                   and (parsed.port or 5432) == plan.database_port
                   and parsed.path == "/" + plan.database and not parsed.fragment)
        # Bootstrap uses the named private-network target with no driver query
        # overrides (including hostaddr/service). TLS/runtime policy belongs in
        # the separately reviewed deployment configuration, not hidden here.
        matches = matches and not parsed.query
    except (TypeError, ValueError):
        matches = False
    if not matches or issuer != plan.issuer or organization != plan.organization:
        raise ValueError("Explicit bootstrap runtime target mismatch")
    if native_enabled is not False or oidc_enabled is not True:
        raise ValueError("Bootstrap requires explicitly enabled SSO-only authentication")


MARKER = "auth.sso_bootstrap.v1"


def private_path(path: Path, *, directory: bool) -> Path:
    info = path.lstat()
    correct_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (not correct_type or path.is_symlink() or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)):
        raise ValueError("Bootstrap input/output must be privately owned with exact permissions")
    return path.resolve(strict=True)


def write_initial_secret(
    directory: Path, username: str, password: str, created: list[tuple[Path, int, int]],
) -> None:
    target = directory / (username + ".initial-password")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    identity = os.fstat(descriptor)
    created.append((target, identity.st_dev, identity.st_ino))
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(password + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def remove_own_uncommitted_files(created: list[tuple[Path, int, int]]) -> None:
    for path, device, inode in created:
        info = path.lstat()
        if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == (device, inode):
            path.unlink()


async def bootstrap(plan: BootstrapPlan, output: Path | None) -> dict[str, object]:
    from sqlalchemy import func, select, text

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import hash_password
    from app.domains.audit.models import AuditLog
    from app.domains.auth.models import Role, User, UserRole
    from app.domains.auth.oidc.config import fresh_signing_enabled
    from app.domains.auth.oidc.models import OIDCIdentity
    from app.domains.auth.password_policy import (
        load_password_policy,
        record_password,
        validate_new_password,
    )
    from app.domains.auth.session_policy import SystemConfig
    from app.scripts.seed_data import seed_permissions, seed_roles

    ensure_runtime_target(plan, database_url=settings.DATABASE_URL, issuer=settings.MDM_OIDC_ISSUER_URL,
                          organization=settings.MDM_OIDC_ORGANIZATION,
                          native_enabled=settings.MDM_NATIVE_LOGIN_ENABLED, oidc_enabled=settings.MDM_OIDC_ENABLED)
    fresh = fresh_signing_enabled()
    if not fresh:
        if output is None:
            raise ValueError("Local signing-password compatibility mode requires a private delivery directory")
        output = private_path(output, directory=True)
    fingerprint = hashlib.sha256(json.dumps({"plan": plan.model_dump(mode="json"), "output": "oidc_fresh:no-local-credential" if fresh else str(output)},
                                            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    created: list[tuple[Path, int, int]] = []
    commit_started = False
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                             {"key": int.from_bytes(hashlib.sha256(MARKER.encode()).digest()[:8], signed=True)})
            marker = await db.get(SystemConfig, MARKER)
            if marker is not None:
                recorded = json.loads(marker.config_value)
                if recorded["plan_sha256"] != fingerprint:
                    raise ValueError("Different bootstrap request; no automatic overwrite")
                current = []
                for account in plan.accounts:
                    row = (await db.execute(select(User, OIDCIdentity).join(
                        OIDCIdentity, OIDCIdentity.user_id == User.user_id).where(
                            User.username == account.username, OIDCIdentity.issuer == plan.issuer,
                            OIDCIdentity.subject == account.subject))).one_or_none()
                    if row is None:
                        raise ValueError("Existing mapping changed; manual review required")
                    current.append({"username": row.User.username, "user_id": row.User.user_id})
                return {"status": "idempotent", "accounts": current, "credentials_reissued": False}

            if (await db.scalar(select(func.count(User.user_id)))) or (
                    await db.scalar(select(func.count(OIDCIdentity.identity_id)))):
                raise ValueError("Refusing a database with existing identities")
            for table in ("srs.substance", "prs.project", "ars.asset", "mm.material", "eqp.equipment"):
                # Fixed identifiers, never constructed from input; no business data is read.
                if await db.scalar(text("SELECT EXISTS(SELECT 1 FROM " + table + " LIMIT 1)")):
                    raise ValueError("Refusing a database with existing business data")
            await seed_permissions(db)
            await seed_roles(db)
            role = (await db.execute(select(Role).where(Role.role_code == "SYS_ADMIN", Role.deleted_at.is_(None)))).scalar_one()
            policy = await load_password_policy(db)
            users = {}
            for account in plan.accounts:
                length = max(32, policy.min_length)
                password = "Aa1!" + "".join(secrets.choice(string.ascii_letters + string.digits + "-_") for _ in range(length - 4))
                if not fresh:
                    await validate_new_password(db, password)
                    assert output is not None
                    write_initial_secret(output, account.username, password, created)
                # Legacy NOT NULL column: hash an unpredictable disposable value,
                # never deliver it or permit it as a login/signature credential.
                user = User(username=account.username, email=str(account.email), full_name=account.full_name,
                            password_hash=hash_password(password), status="active", force_password_change=not fresh,
                            password_changed_at=None if fresh else datetime.now(UTC),
                            password_expires_at=None if fresh else datetime.now(UTC) + timedelta(hours=24),
                            created_by=None, updated_by=None)
                db.add(user)
                await db.flush()
                if not fresh:
                    await record_password(db, user)
                db.add(UserRole(user_id=user.user_id, role_id=role.role_id, granted_by=None))
                users[account.subject] = user
            authorizer = users[plan.operator_subject]
            result = []
            for account in plan.accounts:
                user = users[account.subject]
                # The legacy FK names the explicitly nominated authorizing admin.
                # Actual execution is separately recorded as an OS/CLI operation,
                # never a fabricated human SSO login or electronic signature.
                db.add(OIDCIdentity(issuer=plan.issuer, subject=account.subject, user_id=user.user_id,
                                    created_by=authorizer.user_id, change_reason=plan.reason))
                db.add(AuditLog(user_id=None, username="deployment.cli", action="CREATE", entity_schema="auth",
                               entity_table="user", entity_id=user.user_id, reason=plan.reason,
                               change_summary="首次空库：显式SSO管理员，签名使用Casdoor新鲜认证" if fresh else "首次空库：显式SSO管理员与强制改密签名凭据初始化",
                               extra={"actor_kind": "deployment_cli", "operator_ref": plan.operator_ref,
                                      "executing_uid": os.getuid(), "authorizing_subject": plan.operator_subject,
                                      "authorizing_mdm_user_id": authorizer.user_id, "subject": account.subject,
                                      "issuer": plan.issuer, "organization": plan.organization, "granted_role": "SYS_ADMIN",
                                      "native_auth_enabled": False, "initial_password_hours": 0 if fresh else 24,
                                      "local_signing_credential_created": not fresh}))
                result.append({"username": user.username, "user_id": user.user_id})
            db.add(SystemConfig(config_key=MARKER, config_value=json.dumps({"plan_sha256": fingerprint}),
                                value_type="json", description="首次显式SSO管理员初始化幂等标记", is_sensitive=True))
            await db.flush()
            commit_started = True
            await db.commit()
            return {"status": "created", "accounts": result, "credentials_reissued": False,
                    "initial_password_hours": 0 if fresh else 24, "must_change_password": not fresh, "native_auth_enabled": False,
                    "local_signing_credential_created": not fresh}
        except BaseException:
            if not commit_started:
                await db.rollback()
                remove_own_uncommitted_files(created)
            # After COMMIT starts its outcome can be uncertain. Preserve files and
            # require state inspection; never destroy the only delivery copy.
            raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--secret-output-dir", type=Path, help="Required only by local signing-password compatibility mode")
    parser.add_argument("--apply", action="store_true", help="Requires separate authorization for credential generation/delivery")
    args = parser.parse_args(argv)
    try:
        if os.name != "posix":
            raise ValueError("Run only inside the controlled Linux application runtime")
        path = private_path(args.plan, directory=False)
        if path.stat().st_size > 65536:
            raise ValueError("Plan too large")
        plan = BootstrapPlan.model_validate_json(path.read_text(encoding="utf-8"))
        result = asyncio.run(bootstrap(plan, args.secret_output_dir)) if args.apply else {"status": "validated", "applied": False}
    except Exception:
        print(json.dumps({"status": "rejected", "message": "Bootstrap not confirmed; inspect target and transaction before retry"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
