"""Prepare or install one explicitly selected JSON dungeon configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from wakfu_server.maps.dungeon_runtime_config import (
    prepare_configuration,
    install_configuration,
)


def checked_json(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Evidence hash mismatch: {path.name}")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiled", "topology", "routes", "native_monsters"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
        parser.add_argument("--" + name.replace("_", "-") + "-sha256", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    inputs = {
        name: checked_json(getattr(args, name), getattr(args, name + "_sha256"))
        for name in ("compiled", "topology", "routes", "native_monsters")
    }
    plans = [
        plan for plan in inputs["compiled"]["dungeons"] if plan["slug"] == args.slug
    ]
    if len(plans) != 1:
        raise ValueError("Selected dungeon is absent or ambiguous")
    plan = plans[0]
    routes = [
        route
        for route in inputs["routes"]
        if route["definition_id"] == plan["definition_id"]
    ]
    if len(routes) != 1:
        raise ValueError("Selected native route is absent or ambiguous")
    native = {
        monster["ref"]: monster for monster in inputs["native_monsters"]["monsters"]
    }
    for room in plan["rooms"]:
        for monster in room["monsters"]:
            ref = native.get(monster["ref_id"])
            if ref is None or (ref["min_level"], ref["max_level"]) != (
                monster["native_min_level"],
                monster["native_max_level"],
            ):
                raise ValueError(
                    "Compiled roster contradicts authoritative native monster bounds"
                )
    config = prepare_configuration(
        plan,
        inputs["topology"],
        routes[0],
        version=args.version,
        provenance=args.provenance,
    )
    args.output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    if args.apply:
        from wakfu_server.storage.store import Store

        store = Store(os.environ["WAKFU_DATABASE_URL"])
        try:
            with store.connection() as db:
                install_configuration(db, config)
        finally:
            store.close()
    print(
        json.dumps(
            {
                "slug": args.slug,
                "version": args.version,
                "applied": args.apply,
                "configuration_sha256": hashlib.sha256(
                    args.output.read_bytes()
                ).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
