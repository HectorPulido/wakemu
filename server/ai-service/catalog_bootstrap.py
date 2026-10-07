"""Load the complete authoritative world catalogue directly into AI storage."""
import argparse
import hashlib
import json
from pathlib import Path

from context_store import ContextStore
from world_bridge import CompleteContextExporter, _json_bytes


def provision(roots, store):
    exporter = CompleteContextExporter(roots)
    manifest, sources = exporter.inventory()
    for entry in manifest["entries"]:
        store.import_file(sources[entry["sha256"]], entry["sha256"], entry["size"])
    payload = _json_bytes(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    store.put(digest, len(payload), 0, payload)
    result = store.manifest(digest)
    if not result["complete"]:
        raise ValueError("Incomplete provisioned catalogue")
    return dict(
        sha256=digest,
        entries=result["entries"],
        bytes=sum(entry["size"] for entry in manifest["entries"]),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/native")
    parser.add_argument("--store", default="/tmp/wakfu-ai-context")
    args = parser.parse_args()
    root = Path(args.root)
    result = provision(
        {"catalog": root / "protocol", "engine": root / "wakfu_server", "server": root},
        ContextStore(args.store),
    )
    print(json.dumps(result, sort_keys=True))
