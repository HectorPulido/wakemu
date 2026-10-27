#!/usr/bin/env python3
"""Inspect or switch the local AI backend without interrupting a pinned turn."""
import argparse
import importlib.util
import json
from pathlib import Path
import socket
import struct
import sys
import time


def _repository():
    for parent in Path(__file__).resolve().parents:
        if (parent / "server" / "ai-service").is_dir():
            return parent
    return None


def _selector():
    source = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "wakfu_ai" / "bridge" / "backend_selection.py"
        if candidate.is_file():
            source = candidate
            break
    if source is None:
        raise ValueError("Cannot locate the AI SDK backend selector")
    spec = importlib.util.spec_from_file_location("wakemu_backend_selection", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_health(host, port, backend, timeout):
    """Require the expected framed AI service, with one absolute wall deadline."""
    deadline = time.monotonic() + timeout

    def limit(peer):
        available = deadline - time.monotonic()
        if available <= 0:
            raise TimeoutError("AI health deadline reached")
        peer.settimeout(available)

    def read(peer, size):
        parts = []
        while size:
            limit(peer)
            part = peer.recv(min(size, 65536))
            if not part:
                raise ConnectionError("Incomplete AI health frame")
            parts.append(part)
            size -= len(part)
        return b"".join(parts)

    request = json.dumps(
        dict(id=1, endpoint="/health", payload={}), separators=(",", ":")
    ).encode()
    with socket.create_connection(
        (host, port), timeout=max(0.001, deadline - time.monotonic())
    ) as peer:
        limit(peer)
        peer.sendall(struct.pack("!I", len(request)) + request)
        size = struct.unpack("!I", read(peer, 4))[0]
        if not 0 < size <= 4 * 1024 * 1024:
            raise ValueError("Invalid AI health frame size")
        reply = json.loads(read(peer, size))
        limit(peer)
    expected = "wakfu-ai" if backend == "current" else "wakfu-ai-jondo"
    if (
        not isinstance(reply, dict)
        or set(reply) != {"id", "status", "payload"}
        or type(reply["id"]) is not int
        or reply["id"] != 1
        or type(reply["status"]) is not int
        or reply["status"] != 200
        or not isinstance(reply["payload"], dict)
        or reply["payload"].get("status") != "ok"
        or reply["payload"].get("service") != expected
        or reply["payload"].get("transport") != "tcp"
    ):
        raise ValueError("AI health response does not identify " + expected)


def main(argv=None):
    selector = _selector()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--use", choices=selector.BACKENDS)
    mode.add_argument("--status", action="store_true")
    repository = _repository()
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            repository / ".local-state/wakemu/world/ai-backend.json"
            if repository is not None
            else Path("/data/ai-backend.json")
        ),
    )
    parser.add_argument(
        "--health-host",
        help="Reachable host for the chosen service; use its Docker DNS name inside World",
    )
    parser.add_argument("--health-port", type=int)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        if args.status:
            config = selector.read_config(args.config)
            print(
                json.dumps(
                    dict(
                        config,
                        endpoint=selector.endpoint_for(config["backend"]),
                        config=str(args.config),
                        activation="next_actor_turn",
                    )
                )
            )
            return 0
        if not 0 < args.timeout <= 30:
            raise ValueError("Health timeout must be positive and at most 30 seconds")
        port = (
            args.health_port
            if args.health_port is not None
            else (8090 if args.use == "current" else 8091)
        )
        if not 1 <= port <= 65535:
            raise ValueError("Invalid backend health port")
        host = args.health_host or (
            ("ai" if args.use == "current" else "ai-jondo")
            if repository is None
            else "127.0.0.1"
        )
        # Reachability alone cannot certify the requested service's protocol.
        check_health(host, port, args.use, args.timeout)
        selector.write_config(args.config, args.use)
        print(
            json.dumps(
                dict(
                    backend=args.use,
                    endpoint=selector.endpoint_for(args.use),
                    config=str(args.config),
                    activation="next_actor_turn",
                )
            )
        )
        return 0
    except (OSError, ValueError) as error:
        print("AI backend unchanged: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
