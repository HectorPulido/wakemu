"""TCP wire client for legacy AI callers; planning remains in the service."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

_SDK_LOCK = threading.Lock()


def _wire_modules():
    # Standalone World imports do not necessarily put the mounted SDK on
    # sys.path. Load its package without importing any planning implementation.
    with _SDK_LOCK:
        if "wakfu_ai" not in sys.modules:
            directory = Path(__file__).resolve().parents[2] / "ai-service/wakfu_ai"
            spec = importlib.util.spec_from_file_location(
                "wakfu_ai",
                directory / "__init__.py",
                submodule_search_locations=[str(directory)],
            )
            package = importlib.util.module_from_spec(spec)
            sys.modules["wakfu_ai"] = package
            try:
                spec.loader.exec_module(package)
            except BaseException:
                sys.modules.pop("wakfu_ai", None)
                raise
        return (
            importlib.import_module("wakfu_ai.transport.framed"),
            importlib.import_module("wakfu_ai.transport.endpoint"),
        )


def request(endpoint, payload, *, timeout=1):
    framed, endpoints = _wire_modules()
    address = endpoints.tcp_address(
        os.environ.get("WAKFU_AI_URL", endpoints.DEFAULT_ENDPOINT)
    )
    client = framed.FramedClient(*address, timeout=timeout)
    try:
        status, result = client.request(endpoint, payload)
        if status != 200:
            raise ValueError("AI TCP service rejected the request")
        if (
            len(json.dumps(result, separators=(",", ":"), allow_nan=False).encode())
            > 1024 * 1024
        ):
            raise ValueError("AI response exceeds size limit")
        return result
    finally:
        client.close()
