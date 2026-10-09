"""Measure HTTP round trips independently from native AI computation."""
import argparse
import json
import statistics
import time
from wakfu_ai.bridge.world_bridge import ContextTransport


def measure(url, requests):
    results = []
    for persistent in (False, True):
        client = ContextTransport(url, persistent=persistent)
        timings = []
        try:
            for _ in range(requests):
                started = time.monotonic()
                reply = client.request("/v3/context/status", {"objects": []})
                if reply != {"present": []}:
                    raise ValueError("Unexpected context status acknowledgment")
                timings.append((time.monotonic() - started) * 1000)
            results.append(
                dict(
                    persistent=persistent,
                    requests=requests,
                    medianMs=statistics.median(timings),
                    minMs=min(timings),
                    maxMs=max(timings),
                    tcpOpens=client.metrics["tcpOpens"],
                )
            )
        finally:
            client.close()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://ai:8090")
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10000:
        parser.error("requests must be between 1 and 10000")
    print(json.dumps(measure(args.url, args.requests), indent=2))
