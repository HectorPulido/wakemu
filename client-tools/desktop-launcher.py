#!/usr/bin/env python3
"""Prepare and open the integrated native launcher from repository sources."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "client-tools/mini-launcher-desktop"
PACKAGE = ROOT / ".local-state/wakemu/desktop-launcher"
FILES = (
    "launcher_backend.py", "launcher_ui.py", "launcher_entry.py",
    "local_launcher_auth.py", "portable_config.py", "run-client.py",
    "launcher-bridge.py", "requirements.txt", "README.txt",
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_state(package, config_path=None):
    """Keep saved accounts intact; repository launches initially select localhost."""
    backend = load_module("desktop_launcher_backend", SOURCE / "launcher_backend.py")
    backend.ROOT = package
    backend.STATE_PATH = package / "profile/launcher-state.json"
    if backend.STATE_PATH.exists() and config_path is None:
        return
    state = backend.load_state()
    raw = json.loads(config_path.read_text()) if config_path else {}
    if config_path:
        for key in ("install_root", "certificate"):
            if raw.get(key):
                path = Path(raw[key]).expanduser()
                raw[key] = str(path if path.is_absolute() else (config_path.parent / path).resolve())
    host = raw.get("server_host", "127.0.0.1")
    identifier = "configured-" + hashlib.sha256(str(config_path).encode()).hexdigest()[:12] if config_path else "local"
    server = backend.normalize_server(dict(
        id=identifier,
        name=raw.get("server_name", "Wakemu Local" if not config_path else host),
        server_host=host, dispatch_port=raw.get("dispatch_port", 15558),
        game_ports=raw.get("game_ports", [15556]),
        chat_host=raw.get("chat_host", host), chat_port=raw.get("chat_port", 16337),
        api_url=raw.get("api_url", f"http://{host}:18081"),
        http_url=raw.get("http_url", f"http://{host}:18081"),
        shop_url=raw.get("shop_url", f"http://{host}:18083"),
        achievements_url=raw.get("achievements_url", f"http://{host}:18081"),
        certificate=raw.get("certificate", ""),
        install_root=raw.get("install_root", str(ROOT / "client")),
    ))
    state["servers"] = [server] + [s for s in state["servers"] if s["id"] != identifier]
    state["selected_id"] = identifier
    backend.private_write(backend.STATE_PATH, state)



def prepare(package, *, repository_state=True):
    package = package.resolve()
    target = package / "mini-launcher"
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(SOURCE / name, target / name)
    for name in ("Launch.command", "Launch.sh", "Launch.bat"):
        shutil.copy2(SOURCE / name, package / name)
    try:
        import certifi
    except ImportError:
        pass
    else:
        shutil.copy2(certifi.where(), target / "cacert.pem")
    agent_inputs = [ROOT / "client-tools/packaging/package-mini-launcher.py"]
    agent_inputs += [ROOT / "client-tools/java" / name for name in (
        "LocalDesktopFix.java", "OpenPlantingAgent.java", "OpenPlantingAgentRecovery.java",
    )]
    agent_inputs += [ROOT / "client-tools/dropin" / name for name in (
        "DropinNetworkGuard.java", "DropinNetworkGuardTest.java",
    )]
    include_policy = (ROOT / "client/lib/wakfu-client.jar").is_file()
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in agent_inputs) + str(include_policy).encode()).hexdigest()
    receipt = target / "agents/source.sha256"
    names = ("network-guard.jar", "desktop-fix.jar", "open-planting.jar")
    if not receipt.exists() or receipt.read_text() != digest or any(not (receipt.parent / n).exists() for n in names):
        builder = load_module("desktop_agent_builder", agent_inputs[0])
        with tempfile.TemporaryDirectory(prefix="wakemu-launcher-agents-") as tmp:
            archive = Path(tmp) / "agents.zip"
            # The GUI must open before an external client folder is selected.
            # Dungeon instrumentation is disabled by the integrated launcher.
            builder.build(archive, include_dungeon_policy=include_policy)
            receipt.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as bundle:
                for name in names:
                    (receipt.parent / name).write_bytes(bundle.read("mini-launcher/agents/" + name))
        receipt.write_text(digest)
    if sys.platform == "darwin":
        helper_source = SOURCE / "KeychainHelper.swift"
        digest = hashlib.sha256(helper_source.read_bytes()).hexdigest()
        receipt = target / "keychain-source.sha256"
        if not (target / "keychain-helper").exists() or not receipt.exists() or receipt.read_text() != digest:
            subprocess.run(["bash", str(SOURCE / "build-keychain.sh"), str(target)], check=True)
            receipt.write_text(digest)
    if repository_state:
        config = os.environ.get("WAKFU_LAUNCHER_CONFIG")
        seed_state(package, Path(config).resolve() if config else None)
    return package


def export_archive(output):
    """Export one shared source launcher, excluding all mutable user state."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    built = prepare(PACKAGE, repository_state=False)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            bundle.write(built / "mini-launcher" / name, "Wakemu-Launcher/mini-launcher/" + name)
        for path in sorted((built / "mini-launcher/agents").glob("*.jar")):
            bundle.write(path, "Wakemu-Launcher/mini-launcher/agents/" + path.name)
        for name in ("Launch.command", "Launch.sh", "Launch.bat"):
            bundle.write(built / name, "Wakemu-Launcher/" + name)
        for name in ("KeychainHelper.swift", "build-keychain.sh"):
            bundle.write(SOURCE / name, "Wakemu-Launcher/mini-launcher/" + name)
        bundle.write(SOURCE / "README.txt", "Wakemu-Launcher/README.txt")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="Prepare the integrated launcher without opening it.")
    parser.add_argument("--package", action="store_true", help="Export the shared Mac, Windows and Linux source launcher ZIP.")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/distribution/Wakemu-Launcher.zip")
    parser.add_argument("--profile", default="main", help="Use a separate launcher profile.")
    parser.add_argument("--ui-smoke", type=Path, help="Run the offline interface acceptance check and save its screenshot.")
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.profile):
        parser.error("Invalid profile name")
    if args.package:
        print(export_archive(args.output))
        return 0
    root = PACKAGE if args.profile == "main" else PACKAGE / "instances" / args.profile
    package = prepare(root)
    entry = load_module("desktop_entry", SOURCE / "launcher_entry.py")
    interpreter = entry.ensure_python(ROOT / ".local-state/wakemu/launcher-venv")
    if args.prepare_only:
        print(package)
        return 0
    env = dict(os.environ, WAKFU_LAUNCHER_ROOT=str(package))
    command = [str(interpreter), str(package / "mini-launcher/launcher_ui.py")]
    if args.ui_smoke:
        command += ["--ui-smoke", str(args.ui_smoke.resolve())]
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
