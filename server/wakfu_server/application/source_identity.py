"""Source identity for the dispatcher hub and its extracted application code.

This module must remain importable without starting World or opening a database.
The receipt field remains ``dispatcher_sha256``. A monolithic source tree has
its original single-file SHA; an extracted tree uses a framed source inventory.
Old receipts therefore still require their original source (or the existing
explicit source-drift option), rather than bypassing application source checks.
"""

from hashlib import sha256
from pathlib import Path


def dispatcher_source_sha256(server_root=None):
    """Hash source bytes and names, including added/deleted application modules."""
    server = (
        Path(__file__).resolve().parents[2]
        if server_root is None
        else Path(server_root)
    )
    hub = server / "local_game_server.py"
    application = server / "wakfu_server" / "application"
    modules = sorted(application.rglob("*.py"))
    if not modules:
        return sha256(hub.read_bytes()).hexdigest()
    checksum = sha256(b"wakemu-dispatcher-source-inventory-v1\0")
    for path in (hub, *modules):
        name = path.relative_to(server).as_posix().encode("utf8")
        source = path.read_bytes()
        checksum.update(len(name).to_bytes(8, "big"))
        checksum.update(name)
        checksum.update(len(source).to_bytes(8, "big"))
        checksum.update(source)
    return checksum.hexdigest()
