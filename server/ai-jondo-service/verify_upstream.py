"""Verify pinned upstream sources and explicitly identified local extensions."""
import hashlib
import json
from pathlib import Path


def verify(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    manifest = json.loads((root / "upstream-provenance.json").read_text())
    if manifest["commit"] != "cc58d8996d952f3adff2f6a14f13bdd39964506c":
        raise ValueError("Unexpected Jondo upstream commit")
    for row in manifest["files"]:
        path = (root / row["file"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Upstream provenance path escaped service")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Vendored upstream source changed: " + row["file"])
    return manifest


if __name__ == "__main__":
    manifest = verify()
    extended = sum("local_extension" in row for row in manifest["files"])
    print(
        f"Verified {len(manifest['files']) - extended} unchanged sources and {extended} pinned local extensions at {manifest['commit']}"
    )
