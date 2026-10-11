"""Read-only optional profiler adapter with a bounded upstream request."""
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def snapshot():
    base = os.environ.get("WAKFU_ADMIN_PROFILER_URL", "http://profiler:8092").rstrip(
        "/"
    )
    result = dict(available=False, status=None, report=None)
    for endpoint in ("status", "report"):
        try:
            with urlopen(base + "/" + endpoint, timeout=2) as response:
                payload = response.read(2 * 1024 * 1024 + 1)
            if len(payload) > 2 * 1024 * 1024:
                raise ValueError("Profiler response exceeds inspection limit")
            result[endpoint] = json.loads(payload)
            result["available"] = True
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            pass
    if result["report"] is None:
        try:
            path = Path(
                os.environ.get(
                    "WAKFU_ADMIN_PROFILER_REPORT", "/metrics/performance-latest.json"
                )
            )
            if path.stat().st_size <= 2 * 1024 * 1024:
                result["report"] = json.loads(path.read_text())
                result["available"] = True
                result["report_age_seconds"] = max(
                    0, time.time() - path.stat().st_mtime
                )
                result["report_source"] = "world metrics file"
        except (OSError, ValueError):
            pass
    if not result["available"]:
        result[
            "error"
        ] = "Profiler is unavailable; the server can continue running without it."
    return result
