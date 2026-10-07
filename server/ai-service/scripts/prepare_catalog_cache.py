"""SDK-only catalogue preparation; no encounter or world service mutation."""
import json

from wakfu_ai.bridge.world_entry import native_exporter


def main():
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


if __name__ == "__main__":
    main()
