"""Run selected dungeon gate on the single world, restoring captured r19 config."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--image", required=True)
parser.add_argument("--candidate-db", required=True)
parser.add_argument("--config", type=Path, required=True)
parser.add_argument("--config-sha256", required=True)
parser.add_argument("--phase", choices=("entry", "full"), default="entry")
parser.add_argument("--bundle", type=Path)
parser.add_argument("--bundle-sha256")
args = parser.parse_args()
if (
    not args.candidate_db.startswith("wakemu_candidate_smoke_")
    or not args.candidate_db.replace("_", "").isalnum()
):
    raise ValueError("Disposable candidate database name required")
if hashlib.sha256(args.config.read_bytes()).hexdigest() != args.config_sha256:
    raise ValueError("Selected configuration artifact hash mismatch")
selected_config = json.loads(args.config.read_text())
if bool(args.bundle) != bool(args.bundle_sha256):
    raise ValueError("Bundle and exact hash must be supplied together")
if args.bundle:
    if hashlib.sha256(args.bundle.read_bytes()).hexdigest() != args.bundle_sha256:
        raise ValueError("Bundle artifact hash mismatch")
    bundle = json.loads(args.bundle.read_text())
    if selected_config not in bundle.get("configurations", []):
        raise ValueError("Selected configuration is not in the verified bundle")
elif selected_config["route"]["key"] != "jalato_normal":
    raise ValueError("A general route requires a committed registry bundle")
root = Path.cwd()
artifacts = root / ".runtime/local/dungeon-tls-gate"


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


baseline = json.loads(
    subprocess.check_output(["docker", "compose", "config", "--format", "json"])
)
world = baseline["services"]["world"]
if not world["image"].endswith("-r19"):
    raise ValueError(
        "Expected the captured main Compose baseline to select r19 before running"
    )
# JSON is valid Compose YAML. Capture baseline environment and image so cleanup
# cannot inadvertently restore a concurrently changed candidate configuration.
restore = artifacts / "restore-compose.json"
restore.write_text(
    json.dumps(
        {
            "services": {
                "world": {"image": world["image"], "environment": world["environment"]}
            }
        }
    )
)
override = artifacts / "candidate-compose.json"
override.write_text(
    json.dumps(
        {
            "services": {
                "world": {
                    "image": args.image,
                    "environment": {
                        "WAKFU_DATABASE_URL": f"host=postgres dbname={args.candidate_db} user=wakemu",
                        "WAKFU_REDIS_URL": "redis://redis:6379/15",
                        "PYTHONUNBUFFERED": "1",
                    },
                }
            }
        }
    )
)
result = {
    "passed": False,
    "phase": args.phase,
    "candidate_db": args.candidate_db,
    "candidate_image": args.image,
    "restore_image": world["image"],
    "route_key": selected_config["route"]["key"],
    "slug": selected_config["slug"],
    "bundle_hash": args.bundle_sha256,
}


def error_metadata(error):
    # Do not serialize subprocess commands, environment or packet payloads.
    details = {"type": type(error).__name__}
    if isinstance(error, subprocess.CalledProcessError):
        details["returncode"] = error.returncode
    elif isinstance(error, subprocess.TimeoutExpired):
        details["timeout_seconds"] = error.timeout
    else:
        details["message"] = str(error)
    return details


try:
    run(
        [
            "docker",
            "compose",
            "-f",
            "compose.yaml",
            "-f",
            str(override),
            "up",
            "-d",
            "--no-deps",
            "world",
        ]
    )
    for name in (
        "candidate_shared_combat_push_smoke.py",
        "candidate_shared_combat_three_peer_smoke.py",
        "three_peer_harness.py",
        "tls_smoke_io.py",
        "candidate_dungeon_socket_smoke.py",
        "dungeon_combat_harness.py",
        "candidate_session_lease.py",
    ):
        run(
            [
                "docker",
                "cp",
                str(root / "server/tools" / name),
                "wakfu-local-world-1:/app/tools/",
            ]
        )
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        ready = (
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "wakfu-local-world-1",
                    "python3",
                    "-c",
                    'import socket; s=socket.socket(); raise SystemExit(s.connect_ex(("127.0.0.1",15556)))',
                ],
                capture_output=True,
            ).returncode
            == 0
        )
        if ready:
            break
        time.sleep(1)
    else:
        raise RuntimeError(
            "Candidate listener did not become ready; preserving captured cleanup"
        )
    run(
        [
            "docker",
            "cp",
            str(args.config.resolve()),
            "wakfu-local-world-1:/tmp/dungeon-gate-config.json",
        ]
    )
    installer = """import json,os
from psycopg.conninfo import conninfo_to_dict
from wakfu_server.store import Store
from wakfu_server.maps.dungeon_runtime_config import install_configuration
url=os.environ['WAKFU_DATABASE_URL']
if not conninfo_to_dict(url).get('dbname','').startswith('wakemu_candidate_smoke_'):
 raise ValueError('Candidate database guard failed before configuration installation')
store=Store(url,password_file=os.environ['WAKFU_DATABASE_PASSWORD_FILE'])
try:
 with store.connection() as db:
  install_configuration(db,json.load(open('/tmp/dungeon-gate-config.json')))
finally:
 store.close()
"""
    if args.bundle:
        run(
            [
                "docker",
                "cp",
                str(args.bundle.resolve()),
                "wakfu-local-world-1:/tmp/dungeon-gate-bundle.json",
            ]
        )
        installer = installer.replace(
            "from wakfu_server.maps.dungeon_runtime_config import install_configuration",
            "from tools.install_dungeon_bulk import install_bundle",
        )
        installer = installer.replace(
            "install_configuration(db,json.load(open('/tmp/dungeon-gate-config.json')))",
            "install_bundle(db,json.load(open('/tmp/dungeon-gate-bundle.json')))",
        )
    run(
        [
            "docker",
            "exec",
            "-e",
            "PYTHONPATH=/app:/app/tools",
            "wakfu-local-world-1",
            "python3",
            "-c",
            installer,
        ]
    )
    if args.bundle:
        run(
            [
                "docker",
                "compose",
                "-f",
                "compose.yaml",
                "-f",
                str(override),
                "restart",
                "world",
            ]
        )
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if (
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "wakfu-local-world-1",
                        "python3",
                        "-c",
                        'import socket; s=socket.socket(); raise SystemExit(s.connect_ex(("127.0.0.1",15556)))',
                    ],
                    capture_output=True,
                ).returncode
                == 0
            ):
                break
            time.sleep(1)
        else:
            raise RuntimeError(
                "Candidate registry reload listener did not become ready"
            )
    with (artifacts / f"{args.phase}-tls.log").open("w") as log:
        run(
            [
                "docker",
                "exec",
                "-e",
                "PYTHONPATH=/app:/app/tools",
                "wakfu-local-world-1",
                "python3",
                "/app/tools/candidate_dungeon_socket_smoke.py",
                "--phase",
                args.phase,
                "--route-key",
                selected_config["route"]["key"],
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=3600 if args.phase == "full" else 240,
        )
    result["passed"] = True
except Exception as error:
    result["phase_error"] = error_metadata(error)
    raise
finally:
    # Capture the candidate's logs while it still occupies the single world.
    # Keep this private artifact out of terminal output and version control.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    world_log = artifacts / f"{args.phase}-world-{timestamp}.log"
    try:
        with world_log.open("w") as log:
            collected = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "compose.yaml",
                    "-f",
                    str(override),
                    "logs",
                    "--no-color",
                    "--timestamps",
                    "world",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
        result["world_log"] = str(world_log.relative_to(root))
        result["world_log_returncode"] = collected.returncode
    except Exception as error:
        result["world_log_error"] = error_metadata(error)
    try:
        run(
            [
                "docker",
                "compose",
                "-f",
                "compose.yaml",
                "-f",
                str(restore),
                "up",
                "-d",
                "--no-deps",
                "world",
            ]
        )
        result["restore_requested"] = True
    except Exception as error:
        result["restore_error"] = error_metadata(error)
        raise
    finally:
        (artifacts / f"{args.phase}-tls-result.json").write_text(
            json.dumps(result) + "\n"
        )
