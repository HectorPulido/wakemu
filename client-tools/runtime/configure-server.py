#!/usr/bin/env python3
"""Create a private repository launcher configuration for an explicit server."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client-tools/dropin"))
from portable_config import _server_name
from urllib.parse import urlsplit


def configure(server=None, config_file=None, api_url=None):
    config = json.loads(Path(config_file).read_text()) if config_file else {}
    base = Path(config_file).resolve().parent if config_file else ROOT
    if server is not None:
        config["server_host"] = _server_name(server)
        config.pop("api_url", None)
    config["server_host"] = _server_name(config.get("server_host", "127.0.0.1"))
    if api_url is not None:
        config["api_url"] = api_url
    config.setdefault("api_url", f"http://{config['server_host']}:18081")
    parsed = urlsplit(config["api_url"])
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname != config["server_host"]
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("api_url must use the configured server hostname")
    for name, default in (
        (
            "runtime_root",
            ROOT / ".local-state/wakemu/client-servers" / config["server_host"],
        ),
        ("install_root", ROOT),
        ("runner", ROOT / "client-tools/local-client.sh"),
    ):
        path = Path(config.get(name, default)).expanduser()
        config[name] = str(path if path.is_absolute() else (base / path).resolve())
    output = (
        ROOT / ".local-state/wakemu/client-servers" / (config["server_host"] + ".json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # A configuration contains no account credentials; still keep it private.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--api-url")
    args = parser.parse_args()
    print(configure(args.server, args.config, args.api_url))
