"""SDK-only catalogue preparation; no encounter or world service mutation."""
import argparse
import json
import os
import time

from wakfu_ai.bridge.world_entry import native_exporter, context_transport
from wakfu_ai.transport.endpoint import DEFAULT_ENDPOINT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seal",
        action="store_true",
        help="Publish and seal the complete catalogue before combat.",
    )
    args = parser.parse_args()
    started = time.monotonic()
    exporter = native_exporter()
    if args.seal:
        transport = context_transport(
            os.environ.get("WAKFU_AI_URL", DEFAULT_ENDPOINT), timeout=60
        )
        try:
            digest = transport.catalog(exporter)
            print(
                json.dumps(
                    dict(
                        sha256=digest,
                        complete=True,
                        elapsedMs=(time.monotonic() - started) * 1000,
                        transportMetrics=transport.metrics,
                    )
                )
            )
        finally:
            transport.close()
        return
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
