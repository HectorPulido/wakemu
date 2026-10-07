"""Check server network settings from Compose's .env without executing it."""
import argparse
import ipaddress
import json
import os
from pathlib import Path


def configuration(path, environment):
    values = {}
    if path.is_file():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, separator, value = line.partition("=")
            name = name.strip()
            if not separator:
                raise ValueError(f"Invalid environment assignment on line {number}")
            if name not in (
                "WAKFU_BIND_HOST",
                "WAKFU_ADVERTISE_HOST",
                "WAKFU_ADVERTISE_WORLD_PORT",
            ):
                continue
            value = value.strip()
            if value.startswith(("'", '"')):
                closing = value.find(value[0], 1)
                if closing < 0:
                    raise ValueError(f"Unclosed network setting on line {number}")
                tail = value[closing + 1 :].strip()
                if tail and not tail.startswith("#"):
                    raise ValueError(f"Invalid network setting on line {number}")
                value = value[1:closing]
            else:
                value = value.split(" #", 1)[0].rstrip()
            values[name] = value
    values.update(environment)
    bind = ipaddress.IPv4Address(values.get("WAKFU_BIND_HOST", "0.0.0.0"))
    advertised = ipaddress.IPv4Address(values.get("WAKFU_ADVERTISE_HOST", "127.0.0.1"))
    port = int(values.get("WAKFU_ADVERTISE_WORLD_PORT", "15556"))
    if bind.is_multicast or advertised.is_unspecified or advertised.is_multicast:
        raise ValueError("Invalid bind or advertised server address")
    if not 1 <= port <= 65535:
        raise ValueError("Invalid advertised world port")
    return dict(
        bind_host=str(bind),
        advertised_host=str(advertised),
        advertised_world_port=port,
        note="Compose publishes localhost ports by default; an advertised IP does not change published bindings.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", type=Path, default=Path(__file__).resolve().parents[2] / ".env"
    )
    args = parser.parse_args()
    try:
        result = configuration(args.env_file, os.environ)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
