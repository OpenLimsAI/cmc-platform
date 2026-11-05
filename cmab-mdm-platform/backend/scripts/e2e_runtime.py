"""Disposable local E2E lifecycle. No production configuration is accepted.

Run from backend: python -m scripts.e2e_runtime --help
Credentials live only in the driver, container environments and tmpfs. The
host ledger contains resource IDs, source paths and non-secret evidence only.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LABEL = "mdm.test.run"
BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND.parent


def identity_profile(name):
    """Select only a fixed, explicitly requested synthetic identity profile."""
    if name == "official-v4":
        return {}
    if name == "restricted-v11":
        return {
            "idp_image": "sha256:56e11171cfb2022215a46e2c55b15c9c5734162bdd2f058892cde29e356d42ca",
            "approved_own_policy_v9": True,
            "dcr_self_logout_clients": ("mdm-signing-login", "mdm-signing-portal", "mdm-signing-pm"),
        }
    raise ValueError("Only official-v4 or restricted-v11 synthetic profiles are accepted")


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    artifacts_root: Path
    port_offset: int = 0
    loopback_host: str = "localhost"

    def __post_init__(self):
        if not re.fullmatch(r"mdm-e2e-[a-z0-9][a-z0-9-]{0,39}", self.run_id):
            raise ValueError("Use a new mdm-e2e- run ID, never an environment name")
        if self.port_offset not in {0, 100}:
            raise ValueError("Only the original or independent loopback port set is permitted")
        if self.loopback_host not in {"localhost", "127.0.0.1"}:
            raise ValueError("Only explicit loopback browser hosts are permitted")

    @property
    def port_bindings(self):
        return {key: f"127.0.0.1:{port + self.port_offset}" for key, port in
                {"idp": 19081, "mdm": 19090, "pm": 19091, "portal": 19092}.items()}

    def origin(self, application):
        return "http://" + self.loopback_host + ":" + self.port_bindings[application].rsplit(":", 1)[1]

    @property
    def client_names(self):
        return ("mdm-signing-login", "mdm-signing-proof", "mdm-signing-pm", "mdm-signing-portal", "mdm-signing-pm-delegation")

    @property
    def directory(self):
        return self.artifacts_root.resolve() / self.run_id

    @property
    def internal(self):
        return self.run_id + "-internal"

    def output(self, relative):
        if Path(relative).is_absolute():
            raise ValueError("Artifact path must be relative")
        target = (self.directory / relative).resolve()
        if not target.is_relative_to(self.directory):
            raise ValueError("Artifact path escapes the owned run")
        return target


def validate_fixture(fixture):
    if fixture.get("syntheticOnly") is not True or set(fixture.get("users", {})) != {"signer", "other"}:
        raise ValueError("Only the two explicitly synthetic identities are accepted")
    for name, item in fixture["users"].items():
        if item.get("username") != "e2e." + name or not isinstance(item.get("password"), str) or not 32 <= len(item["password"]) <= 128:
            raise ValueError("Unexpected synthetic identity or password shape")


def validate_owned_resources(manifest, containers, networks):
    run_id = manifest["run_id"]
    expected = manifest["containers"]
    for item in containers:
        name = item["Name"].removeprefix("/")
        if expected.get(name) != item["Id"] or item["Config"].get("Labels", {}).get(LABEL) != run_id:
            raise ValueError("Container ID or ownership changed; do not stop it")
    for item in networks:
        if item.get("Labels", {}).get(LABEL) != run_id:
            raise ValueError("Network ownership changed")
        if any(member["Name"] not in expected for member in item.get("Containers", {}).values()):
            raise ValueError("Network has an unowned member; do not remove it")


class Runtime:
    def __init__(self, spec, *, pm_root=None, mdm_image="mdm-phase2-unit-tests:latest", pm_image="cmc-pm-phase2-e2e:local"):
        self.spec = spec
        self.pm_root = Path(pm_root).resolve() if pm_root else None
        self.mdm_image, self.pm_image = mdm_image, pm_image
        self.ledger = spec.output("runtime.json")
        self.manifest = json.loads(self.ledger.read_text(encoding="utf-8")) if self.ledger.exists() else {
            "run_id": spec.run_id, "created_at_utc": datetime.now(UTC).isoformat(), "port_bindings": spec.port_bindings, "loopback_host": spec.loopback_host, "phase": "new", "containers": {}, "networks": {}, "pending_action": None,
        }
        if self.manifest["run_id"] != spec.run_id:
            raise ValueError("Run ledger identity mismatch")
        if self.manifest.get("port_bindings", spec.port_bindings) != spec.port_bindings:
            raise ValueError("Run ledger loopback port set mismatch")
        if self.manifest.get("loopback_host", "localhost") != spec.loopback_host:
            raise ValueError("Run ledger browser cookie host mismatch")

    def save(self):
        self.spec.directory.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")

    def checkpoint(self, stage, **fields):
        row = {"time_utc": datetime.now(UTC).isoformat(), "stage": stage, **fields}
        with self.spec.output("events.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)

    def docker(self, *args, data=None, timeout=120):
        creation = None
        if args[:2] == ("run", "-d"):
            creation = ("containers", args[args.index("--name") + 1])
        elif args[:2] == ("network", "create"):
            creation = ("networks", args[-1])
        if creation:
            if self.manifest["pending_action"]:
                raise ValueError("Uncertain previous creation; inspect before retry")
            self.manifest["pending_action"] = {"kind": creation[0], "name": creation[1], "time_utc": datetime.now(UTC).isoformat()}
            self.save()
        try:
            result = subprocess.run(["docker", *args], input=data, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("Docker action outcome uncertain; inspect the ledger target before retry") from None
        if result.returncode:
            raise RuntimeError("Docker action failed; raw arguments and private output suppressed")
        if creation:
            self.manifest[creation[0]][creation[1]] = result.stdout.decode().strip()
            self.manifest["pending_action"] = None
            self.save()
        return result.stdout

    def prepare(self):
        if self.manifest["phase"] != "new" or self.spec.directory.exists():
            raise ValueError("Existing run: inspect or clean it, never reprovision blindly")
        for binding in self.spec.port_bindings.values():
            with socket.socket() as probe:
                probe.settimeout(.3)
                if probe.connect_ex(("127.0.0.1", int(binding.rsplit(":", 1)[1]))) == 0:
                    raise ValueError("An approved loopback port is occupied")
        for image in (self.mdm_image, self.pm_image):
            self.docker("image", "inspect", image)
        self.spec.directory.mkdir(parents=True)
        self.save()
        for name in ("screenshots", "web/mdm", "web/pm", "web/portal", "control"):
            self.spec.output(name).mkdir(parents=True)
        self.docker("network", "create", "--internal", "--label", LABEL + "=" + self.spec.run_id, self.spec.internal)
        password, session_key = secrets.token_hex(30), secrets.token_hex(32)
        pg = self.spec.run_id + "-pg"
        self.docker("run", "-d", "--name", pg, "--network", self.spec.internal, "--network-alias", "postgres", "--label", LABEL + "=" + self.spec.run_id,
                    "--tmpfs", "/var/lib/postgresql/data:rw", "-e", "POSTGRES_USER=cmab_app", "-e", "POSTGRES_PASSWORD=" + password, "postgres:16-alpine")
        self.docker("run", "-d", "--name", self.spec.run_id + "-redis", "--network", self.spec.internal, "--network-alias", "redis", "--label", LABEL + "=" + self.spec.run_id,
                    "redis:7-alpine", "redis-server", "--save", "", "--appendonly", "no")
        for _ in range(30):
            ready = subprocess.run(["docker", "exec", pg, "pg_isready", "-h", "127.0.0.1", "-U", "cmab_app", "-d", "postgres"], capture_output=True, timeout=5)
            if ready.returncode == 0:
                break
            time.sleep(.3)
        else:
            raise RuntimeError("New isolated PostgreSQL not ready")
        self.docker("exec", pg, "psql", "-h", "127.0.0.1", "-U", "cmab_app", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "CREATE ROLE cmab_audit_reader NOLOGIN")
        env = {"POSTGRES_USER": "cmab_app", "POSTGRES_PASSWORD": password, "POSTGRES_DBA_USER": "cmab_app", "POSTGRES_DBA_PASSWORD": password,
               "TEST_DB": "cmab_test", "TEST_DB_HOST": "postgres", "TEST_REDIS_URL": "redis://redis:6379/15", "REDIS_URL": "redis://redis:6379/15",
               "DATABASE_URL": "postgresql+asyncpg://cmab_app:" + password + "@postgres/cmab_test", "DATABASE_URL_SYNC": "postgresql://cmab_app:" + password + "@postgres/cmab_test",
               "SECRET_KEY": session_key, "APP_LOG_LEVEL": "ERROR", "RATE_LIMIT_ENABLED": "false", "PYTHONDONTWRITEBYTECODE": "1"}
        args = ["run", "-d", "--name", self.spec.run_id + "-tools", "--network", self.spec.internal, "--label", LABEL + "=" + self.spec.run_id,
                "--mount", "type=bind,source=" + str(BACKEND) + ",target=/app", "--tmpfs", "/test-runtime:rw", "-w", "/app"]
        for key, value in env.items():
            args.extend(["-e", key + "=" + value])
        self.docker(*args, "--entrypoint", "sleep", self.mdm_image, "infinity")
        script = (BACKEND / "scripts/run_tests.sh").read_bytes().replace(b"\r\n", b"\n")
        self.docker("exec", "-i", self.spec.run_id + "-tools", "python", "-c", "import sys;open('/test-runtime/run_tests.sh','wb').write(sys.stdin.buffer.read())", data=script)
        public = self.docker("exec", self.spec.run_id + "-tools", "python", "-c", "from cryptography.hazmat.primitives.asymmetric import rsa;from cryptography.hazmat.primitives import serialization as s;from pathlib import Path;p=Path('/test-runtime/handoff.pem');k=rsa.generate_private_key(public_exponent=65537,key_size=4096);p.write_bytes(k.private_bytes(s.Encoding.PEM,s.PrivateFormat.PKCS8,s.NoEncryption()));p.chmod(0o600);print(k.public_key().public_bytes(s.Encoding.PEM,s.PublicFormat.SubjectPublicKeyInfo).decode())")
        self.spec.output("fixture-public.pem").write_bytes(public)
        self.manifest["phase"] = "prepared"
        self.save()
        self.checkpoint("prepared", published_ports=[], private_storage="new tmpfs", public_handoff_file="fixture-public.pem")

    def import_fixture(self, encrypted_file):
        if self.manifest["phase"] != "prepared":
            raise ValueError("Fixture import requires a new prepared run")
        sealed = Path(encrypted_file).read_bytes()
        if not 128 <= len(sealed) <= 4096:
            raise ValueError("Unexpected encrypted fixture size")
        code = """import json,sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from scripts.e2e_runtime import validate_fixture
p=Path('/test-runtime/handoff.pem')
k=serialization.load_pem_private_key(p.read_bytes(),password=None)
data=k.decrypt(sys.stdin.buffer.read(),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
fixture=json.loads(data);validate_fixture(fixture)
out=Path('/test-runtime/browser-fixture.json');out.write_bytes(data);out.chmod(0o600);p.unlink()
"""
        self.docker("exec", "-i", self.spec.run_id + "-tools", "python", "-c", code, data=sealed)
        self.manifest["phase"] = "fixture-ready"
        self.save()
        self.checkpoint("fixture_imported", synthetic_users=2, plaintext_on_host=False)

    def verify(self):
        identities = list(self.manifest["containers"].values())
        items = json.loads(self.docker("inspect", *identities)) if identities else []
        networks = []
        for identity in self.manifest["networks"].values():
            networks.extend(json.loads(self.docker("network", "inspect", identity)))
        validate_owned_resources(self.manifest, items, networks)

    def exercise(self, await_seconds):
        """The approved browser adapter writes a result; every terminal path cleans up."""
        try:
            from scripts.e2e_services import up
            up(self)
            result = self.spec.output("browser-result.json")
            deadline = time.monotonic() + min(await_seconds, 2700)
            while not result.exists() and time.monotonic() < deadline:
                from scripts.e2e_control import poll
                poll(self)
                time.sleep(1)
            if not result.exists():
                raise RuntimeError("Browser result missing; no acceptance success is recorded")
            record = json.loads(result.read_text(encoding="utf-8"))
            self.checkpoint("browser_finished", status=record.get("status", "blocked"))
            from scripts.e2e_evidence import collect
            collect(self)
        finally:
            self.cleanup()

    def cleanup(self):
        if self.manifest["pending_action"]:
            raise ValueError("Pending creation has an uncertain outcome; reconcile it before cleanup")
        names = self.manifest["containers"]
        live_ids = self.docker("ps", "-aq", "--filter", "label=" + LABEL + "=" + self.spec.run_id).decode().splitlines()
        containers = json.loads(self.docker("inspect", *live_ids)) if live_ids else []
        networks = []
        for identity in self.manifest["networks"].values():
            current = self.docker("network", "ls", "--filter", "id=" + identity, "--format", "{{.ID}}").strip()
            if current:
                networks.extend(json.loads(self.docker("network", "inspect", identity)))
        validate_owned_resources(self.manifest, containers, networks)
        volumes = {m["Name"] for c in containers for m in c["Mounts"] if m["Type"] == "volume"}
        for volume in volumes:
            users = self.docker("ps", "-a", "--filter", "volume=" + volume, "--format", "{{.Names}}").decode().splitlines()
            if any(user not in names for user in users):
                raise ValueError("Volume has an unowned user")
        order = sorted(containers, key=lambda c: not c["Name"].endswith("-pm"))
        for c in order:
            self.docker("stop", "--time", "8", c["Id"])
            self.docker("rm", "-v", c["Id"])
        for n in networks:
            remaining = json.loads(self.docker("network", "inspect", n["Id"]))[0]
            if remaining.get("Containers"):
                raise ValueError("Network still has members")
            self.docker("network", "rm", n["Id"])
        self.manifest["phase"] = "cleaned"
        self.save()
        remaining = self.docker("ps", "-aq", "--filter", "label=" + LABEL + "=" + self.spec.run_id).decode().splitlines()
        if remaining:
            raise RuntimeError("Owned containers remain after cleanup")
        ports = {}
        for key, binding in self.spec.port_bindings.items():
            with socket.socket() as probe:
                probe.settimeout(.3)
                ports[key] = probe.connect_ex(("127.0.0.1", int(binding.rsplit(":", 1)[1]))) == 0
        receipt = {"time_utc": datetime.now(UTC).isoformat(), "run_id": self.spec.run_id,
                   "containers_removed": len(containers), "networks_removed": len(networks),
                   "owned_containers_remaining": remaining, "ports_still_listening": ports,
                   "credentials_destroyed_with_tmpfs": True}
        self.spec.output("cleanup-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        self.checkpoint("cleaned", **{k: v for k, v in receipt.items() if k not in {"time_utc", "run_id"}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "import-fixture", "up", "exercise", "snapshot", "cleanup", "status"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifacts", type=Path, default=APP / ".local-e2e")
    parser.add_argument("--pm-root", type=Path)
    parser.add_argument("--sealed-fixture", type=Path)
    parser.add_argument("--await-seconds", type=int, default=1500)
    parser.add_argument("--port-offset", type=int, choices=[0, 100], default=0)
    parser.add_argument("--loopback-host", choices=["localhost", "127.0.0.1"], default="localhost")
    parser.add_argument("--identity-profile", choices=["official-v4", "restricted-v11"], default="official-v4")
    parser.add_argument("--password-only-signature", action="store_true", help="Configure only the known synthetic signing form; no grants or credentials change")
    args = parser.parse_args()
    runtime = Runtime(RunSpec(args.run_id, args.artifacts, args.port_offset, args.loopback_host), pm_root=args.pm_root)
    if args.action == "prepare":
        runtime.prepare()
    elif args.action == "import-fixture":
        runtime.import_fixture(args.sealed_fixture)
    elif args.action == "up":
        from scripts.e2e_services import up
        if runtime.manifest.get("identity_profile", args.identity_profile) != args.identity_profile:
            raise ValueError("Cannot change the identity profile of an existing owned run")
        for key, value in identity_profile(args.identity_profile).items():
            setattr(runtime, key, value)
        if args.password_only_signature:
            from scripts.e2e_signature_form import configure_identity_fixture
            runtime.configure_identity_fixture = configure_identity_fixture
            runtime.password_only_signing = True
        runtime.manifest["identity_profile"] = args.identity_profile
        runtime.save()
        up(runtime)
    elif args.action == "exercise":
        runtime.exercise(args.await_seconds)
    elif args.action == "cleanup":
        runtime.cleanup()
    elif args.action == "snapshot":
        from scripts.e2e_evidence import collect
        collect(runtime)
    else:
        print(json.dumps(runtime.manifest, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(json.dumps({"status": "blocked", "error_type": type(error).__name__, "message": str(error) if isinstance(error, ValueError) else "Inspect the owned runtime ledger; private subprocess output suppressed"}))
        raise SystemExit(1) from None
