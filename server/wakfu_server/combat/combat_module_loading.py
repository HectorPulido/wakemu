"""Load one combat code generation before accepting any client requests.

The development source volume is mutable. Lazy imports after a source edit
would otherwise combine a new caller with an old dataclass/handler signature.
Loaded modules remain unchanged until the next explicit process restart.
"""
import hashlib
import importlib
from pathlib import Path


def preload_combat_modules():
    directory = Path(__file__).resolve().parent
    files = sorted(
        path for path in directory.glob("*.py") if not path.name.startswith("_")
    )

    def fingerprint():
        digest = hashlib.sha256()
        for path in files:
            digest.update(path.name.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    before = fingerprint()
    for path in files:
        # Preserve the project's flat import names; importing combat.<module>
        # would create a second, incompatible class identity.
        importlib.import_module("wakfu_server." + path.stem)
    if (
        fingerprint() != before
        or sorted(
            path for path in directory.glob("*.py") if not path.name.startswith("_")
        )
        != files
    ):
        raise RuntimeError(
            "Combat sources changed while loading; restart with stable sources"
        )
    return {"combat_modules": len(files), "combat_source_sha256": before}
