"""Select a sealed compatible publication without invoking the compiler."""
import os
import sys

from wakfu_server import native_catalog
from wakfu_server.native_compiled_catalog import resolve_publication


def main():
    if os.environ.get("WAKFU_COMPILED_CATALOG_REUSE_EXISTING") != "1":
        raise SystemExit(
            "Set WAKFU_COMPILED_CATALOG_REUSE_EXISTING=1 to select existing data"
        )
    header = resolve_publication(source_revision=native_catalog.release())
    print(
        "Reusing an existing compiled catalog: compiler-code changes may not be reflected. "
        "Disable WAKFU_COMPILED_CATALOG_REUSE_EXISTING when recompilation is needed.",
        file=sys.stderr,
        flush=True,
    )
    print(header["generation"], flush=True)


if __name__ == "__main__":
    main()
