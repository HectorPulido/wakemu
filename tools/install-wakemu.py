#!/usr/bin/env python3
"""Install a clean server from this checkout and its public installation pack.

Usage: python3 tools/install-wakemu.py
No client, recovery dump, previous runtime or existing Compose environment is used.
Successful stages are pinned and resumable; this command never deletes volumes.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "wakemu-public-installation-v1"
ZERO_TABLES = (
    "accounts",
    "characters",
    "sessions",
    "inventory_items",
    "inventory_containers",
)
SQL_IMPORT = """import os,sys,pathlib,json,psycopg
password=pathlib.Path(os.environ['WAKFU_DATABASE_PASSWORD_FILE']).read_text().strip()
with psycopg.connect(os.environ['WAKFU_DATABASE_URL'],password=password,autocommit=True) as db:
    db.execute(pathlib.Path(sys.argv[1]).read_text(),prepare=False)
print(json.dumps({'applied':sys.argv[1]}))
"""
ZERO_CHECK = """import os,pathlib,json,psycopg
password=pathlib.Path(os.environ['WAKFU_DATABASE_PASSWORD_FILE']).read_text().strip()
tables=('accounts','characters','sessions','inventory_items','inventory_containers')
with psycopg.connect(os.environ['WAKFU_DATABASE_URL'],password=password) as db:
    counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
    assert not any(counts.values()),'Fresh installation contains player data: '+repr(counts)
out={'database':os.environ['WAKFU_DATABASE_URL'].split('dbname=')[1].split()[0],
     'counts':counts,'zero_player_state':True}
pathlib.Path('/installation-receipts/zero-player-state.json').write_text(json.dumps(out,indent=2)+'\\n')
print(json.dumps(out))
"""
SHOP_CHECK = """import json,sys,urllib.request,pathlib
base='http://127.0.0.1:'+sys.argv[1]
with urllib.request.urlopen(base+'/health',timeout=5) as response:
    assert response.status==200
with urllib.request.urlopen(base+'/item-icons/11387.jpg',timeout=5) as response:
    assert response.status==200 and response.headers.get_content_type()=='image/jpeg'
    assert response.read(2)==b'\\xff\\xd8'
out={'health':200,'icon_reference':11387,'icon_http':200,'icon_jpeg':True}
pathlib.Path(sys.argv[2]).write_text(json.dumps(out,indent=2)+'\\n')
print(json.dumps(out))
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".install-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_child(root, value):
    """Require a real relative artifact without symlink or traversal aliases."""
    if not isinstance(value, str) or "\\" in value:
        raise ValueError("Invalid installation artifact path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise ValueError("Installation artifact must stay inside its pack")
    current = Path(root)
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Installation artifacts cannot be symbolic links")
    if not current.is_file():
        raise ValueError("Installation artifact is missing: " + value)
    return current


def verified_artifact(root, row, digest_key="sha256"):
    path = safe_child(root, row["path"])
    expected = row[digest_key]
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("Invalid installation artifact digest")
    if sha256(path) != expected:
        raise ValueError("Installation artifact digest mismatch: " + row["path"])
    return path


def load_public_manifest(pack):
    manifest_path = safe_child(pack, "manifest.json")
    value = json.loads(manifest_path.read_text())
    if not isinstance(value, dict) or value.get("format") != FORMAT:
        raise ValueError(
            "A public installation pack is required; private captures are not supported"
        )
    if (
        value.get("contains_private_capture") is not False
        or value.get("player_tables_exported") != []
    ):
        raise ValueError(
            "Private installation captures cannot be installed by this command"
        )
    return value, sha256(manifest_path)


def source_inventory(root=ROOT):
    """Hash complete build/helper sources; data chunks have their own pack identity."""
    files = {}
    for prefix in ("server", "tools", "database/shop-assets"):
        for path in sorted((root / prefix).rglob("*")):
            relative = path.relative_to(root)
            if any(
                p in ("__pycache__", ".pytest_cache", ".venv", "venv", ".git")
                for p in relative.parts
            ):
                continue
            if relative.parts[:3] == ("server", "data", "installation"):
                continue
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix not in (".pyc", ".pyo")
            ):
                files[relative.as_posix()] = sha256(path)
    files["compose.install.yaml"] = sha256(root / "compose.install.yaml")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return files, hashlib.sha256(encoded).hexdigest()


def migrations(root=ROOT):
    rows = []
    for path in sorted((root / "server/migrations").glob("[0-9][0-9][0-9]_*.sql")):
        rows.append({"version": path.name[:3], "sha256": sha256(path)})
    if not rows or [int(row["version"]) for row in rows] != list(
        range(1, len(rows) + 1)
    ):
        raise ValueError("Installation migrations must be unique and contiguous")
    return rows


@contextmanager
def installation_lock(state):
    with (state / ".installer.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another installer owns this state directory") from error
        yield


class Installer:
    def __init__(self, args):
        if re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", args.project) is None:
            raise ValueError("Project must be a short lowercase Compose identifier")
        self.args = args
        self.pack = args.data_pack.resolve()
        self.state = args.state_dir.absolute()
        if self.state.is_symlink() or self.state == ROOT:
            raise ValueError(
                "Installation state must be a separate nonsymlink directory"
            )
        self.public, self.pack_sha = load_public_manifest(self.pack)
        self.source_files, self.source_sha = source_inventory()
        self.identity = {
            "project": args.project,
            "database": "wakemu_" + args.project.replace("-", "_"),
            "manifest_sha256": self.pack_sha,
            "source_inventory_sha256": self.source_sha,
        }
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("WAKFU_", "WAKEMU_", "COMPOSE_"))
        }
        self.progress = {
            "installation": self.identity,
            "created_at": now(),
            "stages": {},
        }

    def run(self, key, command, *, repeat=False):
        previous = self.progress["stages"].get(key)
        if previous is not None and not repeat:
            print("Already complete: " + key, flush=True)
            return
        print("Installing: " + key, flush=True)
        started = time.monotonic()
        log = self.state / "receipts" / (key + ".log")
        with log.open("a") as stream:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                if len(line) <= 4096:
                    print(line, end="", flush=True)
                else:
                    print("Detailed output recorded in " + str(log), flush=True)
            code = process.wait()
        if code:
            raise RuntimeError(
                "Installation stage failed: " + key + "; retained log: " + str(log)
            )
        self.progress["stages"][key] = {
            "completed_at": now(),
            "seconds": round(time.monotonic() - started, 3),
            "log": log.name,
            "command": command,
        }
        atomic_json(self.state / "installation.json", self.progress)

    def compose(self, *args):
        return [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(self.state / "compose.env"),
            "--project-name",
            self.args.project,
            "--file",
            str(ROOT / "compose.install.yaml"),
            *args,
        ]

    def helper(self, *args):
        return self.compose(
            "run", "--rm", "--no-deps", "-T", "--entrypoint", "python3", "world", *args
        )

    def install(self):
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        with installation_lock(self.state):
            self._install()

    def _install(self):
        receipt = self.state / "installation.json"
        if receipt.exists():
            self.progress = json.loads(receipt.read_text())
            if self.progress["installation"] != self.identity:
                raise ValueError(
                    "Existing installation is pinned to different source/data; no state was reset"
                )
        else:
            existing = subprocess.check_output(
                [
                    "docker",
                    "volume",
                    "ls",
                    "--quiet",
                    "--filter",
                    "label=com.docker.compose.project=" + self.args.project,
                ],
                env=self.env,
                text=True,
            ).strip()
            containers = subprocess.check_output(
                [
                    "docker",
                    "ps",
                    "--all",
                    "--quiet",
                    "--filter",
                    "label=com.docker.compose.project=" + self.args.project,
                ],
                env=self.env,
                text=True,
            ).strip()
            if existing or containers:
                raise ValueError(
                    "Project already has containers or volumes without an installer receipt; refusing to reuse runtime data"
                )
            atomic_json(receipt, self.progress)
        (self.state / "receipts").mkdir(mode=0o700, exist_ok=True)
        self.run(
            "materialize-public-data",
            [
                sys.executable,
                str(ROOT / "server/tools/materialize_installation_data.py"),
                "--pack",
                str(self.pack),
                "--output",
                str(self.state / "inputs"),
            ],
        )
        inputs = self.state / "inputs"
        seed = json.loads(safe_child(inputs, "manifest.json").read_text())
        if (
            seed.get("format") != "wakemu-installation-seed-v1"
            or seed.get("contains_private_capture") is not False
            or seed.get("player_tables_exported") != []
        ):
            raise ValueError(
                "Materialized installation data must exclude private captures and player tables"
            )
        revisions = {row["revision"]: row for row in seed["releases"]}
        active = seed["active_revision"]
        if active not in revisions or any(
            re.fullmatch(r"[0-9a-f]{64}", value) is None for value in revisions
        ):
            raise ValueError("Invalid materialized catalog revisions")
        bootstrap = seed["bootstrap_export"]
        verified_artifact(inputs, bootstrap, "import_expected_sha256")
        reviewed = seed["reviewed_dungeons"]
        verified_artifact(inputs, reviewed)
        additional = seed.get("additional_seeds", [])
        for row in additional:
            verified_artifact(inputs, row)
        role_revisions = self.public.get("catalogs", {})
        mining = role_revisions.get("mining_revision")
        fishing = role_revisions.get("fishing_revision")
        if mining not in revisions or fishing not in revisions:
            raise ValueError(
                "Both production resource catalog revisions must be present"
            )
        values = {
            "WAKEMU_INSTALL_STATE_DIR": str(self.state),
            "WAKEMU_INSTALL_DATABASE": self.identity["database"],
            "WAKFU_WORLD_IMAGE": "wakemu-install-world:" + self.source_sha[:16],
            "WAKFU_AI_IMAGE": "wakemu-install-ai:" + self.source_sha[:16],
            "WAKFU_SHOP_IMAGE": "wakemu-install-shop:" + self.source_sha[:16],
            "WAKFU_CATALOG_REVISION": active,
            "WAKFU_MINING_CATALOG_REVISION": mining,
            "WAKFU_FISHING_CATALOG_REVISION": fishing,
            "WAKFU_BOOTSTRAP_SOURCE_SHA256": bootstrap["import_expected_sha256"],
            "WAKFU_ADVERTISE_HOST": self.args.advertise_host,
            "WAKEMU_INSTALL_WORLD_PORT": str(self.args.world_port),
            "WAKEMU_INSTALL_DISPATCHER_PORT": str(self.args.dispatcher_port),
            "WAKEMU_INSTALL_HTTP_PORT": str(self.args.http_port),
            "WAKEMU_INSTALL_SHOP_PORT": str(self.args.shop_port),
            "WAKEMU_INSTALL_SHOP_PUBLIC_URL": "http://"
            + self.args.advertise_host
            + ":"
            + str(self.args.shop_port),
        }
        if any(any(c in value for c in "\r\n$") for value in values.values()):
            raise ValueError("Unsafe generated Compose environment value")
        env_file = self.state / "compose.env"
        env_file.write_text("".join(k + "=" + v + "\n" for k, v in values.items()))
        env_file.chmod(0o600)
        prepare = runpy.run_path(str(ROOT / "tools/prepare-local-runtime.py"))
        prepare["prepare"](self.state / "world", self.state / "database")
        prepare["configure_service_user"](self.state / "database", env_file)
        self.run("compose-config", self.compose("config", "--quiet"), repeat=True)
        self.run("build-world", self.compose("build", "world"))
        self.run("build-ai", self.compose("build", "ai"))
        self.run("build-shop", self.compose("build", "shop"))
        self.run(
            "start-storage",
            self.compose("up", "-d", "--no-build", "--wait", "postgres", "redis"),
            repeat=True,
        )
        self.run("migrate-schema", self.helper("/app/tools/migrate_postgres.py"))
        ordered = [value for value in revisions if value != active] + [active]
        for revision in ordered:
            command = [
                "/app/tools/import_native_catalogs.py",
                "--release-manifest",
                "/installation/manifest.json",
                "--expected-revision",
                revision,
                "--directory",
                "/installation/catalogs/" + revision,
            ]
            if revision != active:
                command.append("--stage-only")
            self.run("catalog-" + revision, self.helper(*command))
        self.run(
            "bootstrap",
            self.helper(
                "/app/tools/import_bootstrap_capture.py",
                "--source",
                "/installation/" + bootstrap["path"],
                "--expected-sha256",
                bootstrap["import_expected_sha256"],
                "--capture-key",
                seed.get("bootstrap", {}).get("capture_key", "native-bootstrap-v1"),
            ),
        )
        self.run(
            "reviewed-dungeons",
            self.helper("-c", SQL_IMPORT, "/installation/" + reviewed["path"]),
        )
        for index, row in enumerate(additional):
            self.run(
                "public-seed-" + str(index),
                self.helper("-c", SQL_IMPORT, "/installation/" + row["path"]),
            )
        existing_environmental = "environmental-profiles" in self.progress["stages"]
        self.run(
            "environmental-profiles",
            self.helper("/app/tools/install_environmental_profiles.py", "--activate"),
        )
        # Initial activation already verifies its complete transaction.
        if existing_environmental:
            self.run(
                "environmental-verify",
                self.helper(
                    "/app/tools/install_environmental_profiles.py", "--verify-only"
                ),
                repeat=True,
            )
        self.run("zero-player-state", self.helper("-c", ZERO_CHECK))
        expected = {
            "installation": self.identity,
            "schema_versions": migrations(),
            "native_catalog": {
                "active_revision": active,
                "releases": [
                    {
                        key: row[key]
                        for key in ("revision", "document_count", "source_bytes")
                    }
                    for row in revisions.values()
                ],
                "documents": sum(row["document_count"] for row in revisions.values()),
            },
            "expected_counts": self.public.get("expected_counts", {}),
            "expected_semantics": self.public.get("expected_semantics", {}),
            "required_zero_tables": list(ZERO_TABLES),
            "declared_seed_inputs": [
                {"key": row["path"], "sha256": row["sha256"]}
                for row in [reviewed, *additional]
            ],
        }
        atomic_json(self.state / "receipts/verification-manifest.json", expected)
        self.run(
            "start-world-ai-shop",
            self.compose("up", "-d", "--no-build", "--wait", "ai", "shop", "world"),
            repeat=True,
        )
        print(
            "World is available on localhost:"
            + str(self.args.world_port)
            + "; dispatcher "
            + str(self.args.dispatcher_port),
            flush=True,
        )
        self.run(
            "shop-http-icon",
            [
                sys.executable,
                "-c",
                SHOP_CHECK,
                str(self.args.shop_port),
                str(self.state / "receipts/shop-http-icon.json"),
            ],
            repeat=True,
        )
        if not self.args.skip_login_probe:
            self.run(
                "native-login-reconnect",
                self.compose(
                    "exec",
                    "-T",
                    "world",
                    "python3",
                    "/app/tools/verify_clean_install.py",
                    "--manifest",
                    "/installation-receipts/verification-manifest.json",
                    "--receipt",
                    "/installation-receipts/native-login-reconnect.json",
                ),
            )
        self.progress["status"] = (
            "READY_UNVERIFIED" if self.args.skip_login_probe else "VERIFIED"
        )
        self.progress["completed_at"] = now()
        atomic_json(receipt, self.progress)
        print(
            "Installation "
            + self.progress["status"]
            + "; receipts: "
            + str(self.state / "receipts"),
            flush=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-pack", type=Path, default=ROOT / "server/data/installation"
    )
    parser.add_argument("--project", default="wakemu-install")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--advertise-host", default="127.0.0.1")
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--http-port", type=int, default=18081)
    parser.add_argument("--shop-port", type=int, default=18083)
    parser.add_argument(
        "--skip-login-probe",
        action="store_true",
        help="Leave authentication explicitly unverified",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Inspect inputs without creating state or running Docker",
    )
    args = parser.parse_args(argv)
    if len(
        {args.world_port, args.dispatcher_port, args.http_port, args.shop_port}
    ) != 4 or any(
        not 1 <= value <= 65535
        for value in (
            args.world_port,
            args.dispatcher_port,
            args.http_port,
            args.shop_port,
        )
    ):
        parser.error("Distinct valid HTTP, World and dispatcher ports are required")
    if args.state_dir is None:
        args.state_dir = ROOT / ".local-state/installation" / args.project
    try:
        installer = Installer(args)
        if args.plan:
            print(
                json.dumps(
                    {
                        "installation": installer.identity,
                        "schema_versions": migrations(),
                        "data_pack": str(installer.pack),
                        "state_dir": str(installer.state),
                        "compose": str(ROOT / "compose.install.yaml"),
                    },
                    indent=2,
                )
            )
        else:
            installer.install()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(
            "Installation stopped without resetting state: " + str(error),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
