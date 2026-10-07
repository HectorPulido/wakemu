"""SDK-only catalogue preparation; no encounter or world service mutation."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from world_entry import native_exporter

if __name__ == "__main__":
    exporter = native_exporter()
    manifest, sources = exporter.inventory()
    print(
        json.dumps(
            dict(
                entries=len(manifest["entries"]),
                objects=len(sources),
                bytes=sum(entry["size"] for entry in manifest["entries"]),
            )
        )
    )
