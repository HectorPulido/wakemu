#!/usr/bin/env python3
"""Prepare generated runtime files and private persistent service credentials."""
import argparse
import os
import re
import tempfile
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = (
    "postgres-password",
    "ecology-token",
    "objectives-token",
    "admin-control-token",
)


def prepare(runtime, database):
    runtime = Path(runtime)
    database = Path(database)
    for root in (runtime, database):
        if root.is_symlink():
            raise ValueError("Data roots must not be symbolic links")
    for directory in (
        runtime / "logs",
        database / "secrets",
        database / "secrets/admin",
        database / "secrets/admin-control",
        database / "shop-assets",
        database / "backups",
    ):
        if directory.is_symlink():
            raise ValueError("Runtime directories must not be symbolic links")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    for name in SECRET_NAMES:
        path = database / "secrets" / name
        if path.is_symlink():
            raise ValueError("Secret files must not be symbolic links")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if not path.is_file() or not path.stat().st_size:
                raise ValueError("Existing secret must be a nonempty regular file")
            continue
        with os.fdopen(fd, "w") as target:
            target.write(secrets.token_urlsafe(48) + "\n")
        created.append(name)
    return created


def configure_service_user(database, compose_env_file):
    """Match unprivileged containers to the existing private secret owner."""
    owners = set()
    for name in SECRET_NAMES:
        path = Path(database) / "secrets" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Service credentials must be regular non-symlink files")
        info = path.stat()
        owners.add((info.st_uid, info.st_gid))
    if len(owners) != 1:
        raise ValueError(
            "Service credential owners differ; refusing ambiguous service identity"
        )
    uid, gid = owners.pop()
    target = Path(compose_env_file)
    if target.is_symlink():
        raise ValueError("Compose environment must not be a symbolic link")
    original = target.read_text() if target.exists() else ""
    values = {"WAKFU_SERVICE_UID": str(uid), "WAKFU_SERVICE_GID": str(gid)}
    seen = set()
    lines = []
    pattern = re.compile(
        r"^(\s*(?:export\s+)?)(WAKFU_SERVICE_UID|WAKFU_SERVICE_GID)(\s*=\s*)([^#\r\n]*)(.*)$"
    )
    for line in original.splitlines(keepends=True):
        match = pattern.match(line.rstrip("\r\n"))
        if match:
            key = match.group(2)
            seen.add(key)
            suffix = match.group(5)
            if suffix:
                suffix = " " + suffix.lstrip()
            ending = (
                "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            )
            line = match.group(1) + key + match.group(3) + values[key] + suffix + ending
        lines.append(line)
    text = "".join(lines)
    for key, value in values.items():
        if key not in seen:
            if text and not text.endswith("\n"):
                text += "\n"
            text += key + "=" + value + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".compose-env-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return uid, gid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=ROOT / ".runtime/local")
    parser.add_argument("--database-root", type=Path, default=ROOT / ".database")
    parser.add_argument("--compose-env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    created = prepare(args.runtime_root, args.database_root)
    configure_service_user(args.database_root, args.compose_env_file)
    print(
        "Runtime directories and persistent credentials prepared; existing state preserved."
    )
    print("New secret files: " + (", ".join(created) if created else "none"))
    print(
        "This prepares directories and credentials only; native catalogs and protocol templates are still required."
    )
