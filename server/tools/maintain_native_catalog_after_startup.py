"""Run native payload retention after World is available, in the same container."""

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
    from tools.compact_native_catalog import main as maintain

    maintain()


if __name__ == "__main__":
    main()
