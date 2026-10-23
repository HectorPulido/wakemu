"""Probe the separate AI service over its production TCP framing protocol."""
import json
import os

from .framed import FramedClient


def health(host="127.0.0.1", port=8090, *, timeout=2):
    channel = FramedClient(host, port, timeout=timeout)
    try:
        status, payload = channel.request("/health", {})
        if (
            status != 200
            or not isinstance(payload, dict)
            or payload.get("status") != "ok"
            or payload.get("transport") != "tcp"
        ):
            raise ValueError("AI TCP health probe failed")
        return payload
    finally:
        channel.close()


def main():
    print(
        json.dumps(
            health(
                os.environ.get("WAKFU_AI_HEALTH_HOST", "127.0.0.1"),
                int(os.environ.get("WAKFU_AI_PORT", "8090")),
            ),
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
