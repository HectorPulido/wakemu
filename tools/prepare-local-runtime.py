#!/usr/bin/env python3
"""Create private local runtime directories and secrets without overwriting state."""
import argparse
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def prepare(runtime):
    runtime = Path(runtime)
    for name in ("logs", "secrets"):
        directory = runtime / name
        if directory.is_symlink():
            raise ValueError("Runtime directories must not be symbolic links")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    for name in ("postgres-password", "scheduler-token"):
        path = runtime / "secrets" / name
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=ROOT / ".runtime/local")
    args = parser.parse_args()
    created = prepare(args.runtime_root)
    print("Private runtime prepared; existing state preserved.")
    print("New secret files: " + (", ".join(created) if created else "none"))
    print(
        "This prepares directories and credentials only; native catalogs and protocol templates are still required."
    )
