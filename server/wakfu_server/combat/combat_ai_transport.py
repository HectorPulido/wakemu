"""TCP wire client for legacy AI callers; planning remains in the service."""
import importlib
import json
import os
import threading

_SDK_LOCK = threading.Lock()


def _wire_modules():
    # World owns the framed client, even when the optional Python planner is
    # absent. No planner implementation is imported here.
    with _SDK_LOCK:
        return (
            importlib.import_module(
                "wakfu_server.wakia_bridge.wakfu_ai.transport.framed"
            ),
            importlib.import_module(
                "wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint"
            ),
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
