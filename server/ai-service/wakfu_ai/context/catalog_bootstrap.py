"""Load the complete authoritative world catalogue directly into AI storage."""
import argparse
import hashlib
import json
from pathlib import Path

from .context_store import ContextStore
from ..bridge.world_bridge import CompleteContextExporter, _json_bytes


def provision(roots, store, *, source_only=False):
    exporter = CompleteContextExporter(roots, source_only=source_only)
    manifest, sources = exporter.inventory()
    for entry in manifest["entries"]:
        store.import_file(sources[entry["sha256"]], entry["sha256"], entry["size"])
    payload = _json_bytes(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    store.put(digest, len(payload), 0, payload)
    result = store.manifest(digest)
    if not result["complete"]:
        raise ValueError("Incomplete provisioned catalogue")
    result = dict(
        sha256=digest,
        entries=result["entries"],
        bytes=sum(entry["size"] for entry in manifest["entries"]),
    )
    if source_only:
        result.update(catalog_deferred=True, scope="engine-provenance-only")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/native")
    parser.add_argument("--store", default="/tmp/wakfu-ai-context")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    result = provision(
        {"catalog": root / "protocol", "engine": root / "wakfu_server", "server": root},
        ContextStore(args.store),
        source_only=args.source_only,
    )
    print(json.dumps(result, sort_keys=True))
