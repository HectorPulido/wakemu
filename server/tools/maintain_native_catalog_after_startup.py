"""Compact immutable catalog storage after World opens, in the same container."""

import json
import time
from urllib.error import URLError
from urllib.request import urlopen


def main():
    while True:
        try:
            with urlopen("http://127.0.0.1:18081/health", timeout=2) as response:
                if response.status == 200 and json.load(response).get("ok") is True:
                    break
        except (URLError, OSError, ValueError):
            pass
        time.sleep(1)
    from tools.compact_compiled_bodies import main as compact_compiled
    from tools.compact_native_storage import main as compact_native

    # Each converter keeps legacy interfaces available until its verified,
    # transactional cutover. Native conversion also retires obsolete payloads,
    # avoiding a legacy rewrite immediately before normalized storage.
    compact_compiled()
    compact_native()


if __name__ == "__main__":
    main()
