#!/usr/bin/env python3
"""Build repository agents and launch against a configured private server."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client-tools/dropin"))
from portable_config import settings, profile_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cfg = settings()
    os.environ["WAKFU_SERVER_NAME"] = cfg["server_name"]
    os.environ["WAKFU_SERVER_IPV4"] = cfg["server_host"]
    agents = ROOT / ".runtime/client-servers/agents"
    agents.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        "mini_package", ROOT / "client-tools/packaging/package-mini-launcher.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "agents.zip"
        module.build(archive)
        with zipfile.ZipFile(archive) as bundle:
            for name in ("network-guard.jar", "desktop-fix.jar", "open-planting.jar"):
                (agents / name).write_bytes(bundle.read("mini-launcher/agents/" + name))
    os.environ["WAKFU_AGENT_ROOT"] = str(agents)
    os.environ["WAKFU_REPOSITORY_BRIDGE"] = str(
        ROOT / "client-tools/runtime/local-launcher-bridge.py"
    )
    profile = os.environ.get("WAKFU_LOCAL_PROFILE", "main")
    command = [
        sys.executable,
        str(ROOT / "client-tools/dropin/run-client.py"),
        "--profile",
        profile,
    ]
    if args.check:
        return subprocess.call(command + ["--check"])
    subprocess.run(
        ["bash", str(ROOT / "sniffer/build-capture-agent.sh")], cwd=ROOT, check=True
    )
    os.environ["WAKFU_CAPTURE_AGENT"] = str(ROOT / ".runtime/capture-agent.jar")
    token = os.environ.get("WAKFU_GAME_LOGIN_FILE")
    if not token:
        subprocess.run(
            [sys.executable, str(ROOT / "client-tools/runtime/local-login.py")],
            check=True,
        )
        token = str(profile_root(profile) / "login-session.json")
    return subprocess.call(command + ["--token-file", token])


if __name__ == "__main__":
    raise SystemExit(main())
