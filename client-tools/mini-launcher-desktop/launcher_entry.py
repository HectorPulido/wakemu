#!/usr/bin/env python3
"""Start the shared desktop launcher, installing its isolated GUI dependencies once."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

SOURCE = Path(__file__).resolve().parent


def ensure_python(environment):
    environment = Path(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirements = SOURCE / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    receipt = environment / "launcher-requirements.sha256"
    if python.is_file() and receipt.exists() and receipt.read_text() == digest:
        return python
    # A supplied interpreter with matching dependencies can be reused directly.
    code = "import PySide6,certifi; assert PySide6.__version__ == '6.10.3'"
    if sys.platform == "linux":
        code += "; import keyring,secretstorage"
    if python.is_file() and subprocess.run([str(python), "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        receipt.write_text(digest)
        return python
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    print("Installing the launcher's GUI dependencies in its private environment…", flush=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)], check=True)
    receipt.write_text(digest)
    return python


def ensure_keychain(root):
    if sys.platform != "darwin":
        return
    target = root / "mini-launcher"
    receipt = target / "keychain-source.sha256"
    digest = hashlib.sha256((SOURCE / "KeychainHelper.swift").read_bytes()).hexdigest()
    if not (target / "keychain-helper").is_file() or not receipt.is_file() or receipt.read_text() != digest:
        subprocess.run(["bash", str(SOURCE / "build-keychain.sh"), str(target)], check=True)
        receipt.write_text(digest)


def main():
    root = Path(os.environ.get("WAKFU_LAUNCHER_ROOT", SOURCE.parent)).resolve()
    ensure_keychain(root)
    python = ensure_python(root / ".launcher-env")
    env = dict(os.environ, WAKFU_LAUNCHER_ROOT=str(root))
    return subprocess.call([str(python), str(SOURCE / "launcher_ui.py"), *sys.argv[1:]], env=env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
