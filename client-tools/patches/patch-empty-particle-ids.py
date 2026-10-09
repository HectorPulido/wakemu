#!/usr/bin/env python3
"""Patch the shared native Lua APS helper's documented empty-ID sentinel."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
import zipfile

ORIGINAL = b"if (apsId == nil or apsId == 0) then return end"
PATCHED = b'if (apsId == nil or apsId == 0 or apsId == "") then return end'
MEMBER = "1040.lua"


def patch_archive(path, backup_path=None):
    path = Path(path)
    with zipfile.ZipFile(path) as source:
        script = source.read(MEMBER)
        if PATCHED in script:
            return False
        if script.count(ORIGINAL) != 1:
            raise ValueError("Unknown native 1040.lua APS guard; archive unchanged")
        patched = script.replace(ORIGINAL, PATCHED, 1)
        backup = (
            Path(backup_path)
            if backup_path is not None
            else Path(__file__).resolve().parents[2]
            / ".runtime/client-patches"
            / (
                hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
                + "-"
                + path.name
                + ".before-empty-particle-ids"
            )
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(path, backup)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            staged = Path(temporary.name)
        try:
            with zipfile.ZipFile(staged, "w") as target:
                target.comment = source.comment
                for member in source.infolist():
                    target.writestr(
                        member,
                        patched if member.filename == MEMBER else source.read(member),
                    )
            staged.chmod(path.stat().st_mode)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--backup",
        type=Path,
        help="Original archive backup outside the client directory",
    )
    args = parser.parse_args()
    print("patched" if patch_archive(args.archive, args.backup) else "already patched")
