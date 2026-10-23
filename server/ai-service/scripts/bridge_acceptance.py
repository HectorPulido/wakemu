#!/usr/bin/env python3
"""Transfer and verify every file in real native roots; no synthetic subset."""
import argparse
import hashlib
import json
from pathlib import Path

from wakfu_ai.bridge.world_bridge import CompleteContextExporter
from wakfu_ai.bridge.world_entry import context_transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--catalog-root", required=True)
    parser.add_argument("--engine-root", required=True)
    args = parser.parse_args()
    exporter = CompleteContextExporter(
        dict(catalog=Path(args.catalog_root), engine=Path(args.engine_root))
    )
    manifest, sources = exporter.inventory()
    expected = {
        prefix + "/" + path.relative_to(root).as_posix()
        for prefix, root in exporter.roots.items()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert expected == {entry["path"] for entry in manifest["entries"]}
    transport = context_transport(args.url, timeout=30)
    digest = transport.catalog(exporter)
    sealed = transport.request("/v3/context/manifest", dict(sha256=digest))
    assert sealed["complete"] and not sealed["missing"]
    assert sealed["entries"] == len(expected)
    # A second complete pass uses existing objects, without changing scope or
    # authorizing an incomplete manifest after a mere transport cache hit.
    assert transport.catalog(exporter) == digest
    print(
        json.dumps(
            dict(
                result="complete",
                manifest=digest,
                files=len(expected),
                uniqueContents=len(sources),
                bytes=sum(entry["size"] for entry in manifest["entries"]),
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
